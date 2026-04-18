import logging
import os
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from parser import Section

logger = logging.getLogger("steinbot")

_MAX_CHUNK_CHARS = 200_000   # ~50k tokens at 4 chars/token
_RETRY_WAIT_SECS = 60
_MODEL = "gemini-2.5-flash"

_CHUNK_PROMPT = """\
You are reading a section of a book. Extract the following from this section only:
- Characters introduced or significantly developed (name, role, relationships)
- Key plot events in the order they occur
- Thematic elements present
- New locations, environments, or world-building details introduced in this section

Be thorough but concise. This output will be combined with notes from other sections \
to build a complete book profile.
"""

_REDUCE_PROMPT = """\
You are a literary analyst. Using the per-section notes below, which cover the entire \
book in order, produce a structured reference document with the following five sections. \
Be thorough — this document will be used by an AI assistant to answer reader questions \
about the book.

# Synopsis
A thorough overview of the full plot arc from beginning to end.

# Characters
Key characters: their role, motivations, and relationships to one another. \
Include minor characters as well. Include as much detail as their role in the \
narrative warrants.

# Themes
Major themes and motifs explored throughout the book.

# Setting
Time period, locations, and world-building details relevant to understanding the story. \
You can draw from your own knowledge to fill in the gaps here. \
Only draw from your knowledge for verifiable historical or cultural context.

# Key Events
A chronological list of major plot beats and turning points. Include details that a \
human reader would consider obvious but are necessary to understand character \
motivations, causal links, or narrative logic.
"""


def _generate_content(client, prompt_text: str) -> str:
    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt_text)])],
        )
        return response.text
    except ClientError as e:
        if e.code == 429:
            logger.warning("Rate limited — waiting %ds before retry", _RETRY_WAIT_SECS)
            time.sleep(_RETRY_WAIT_SECS)
            response = client.models.generate_content(
                model=_MODEL,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt_text)])],
            )
            return response.text
        raise


def _split_chunks(text: str) -> list[str]:
    return [text[i : i + _MAX_CHUNK_CHARS] for i in range(0, len(text), _MAX_CHUNK_CHARS)]


def generate_profile(sections: list[Section], epub_path: str) -> str:
    profile_path = os.path.splitext(epub_path)[0] + ".profile.txt"

    if os.path.exists(profile_path):
        logger.debug("Profile already exists at %s — skipping generation", profile_path)
        with open(profile_path) as f:
            return f.read()

    logger.debug("Generating profile for %s", epub_path)
    full_text = "\n\n".join(
        f"## {s.title}\n\n{s.text}" if s.title else s.text
        for s in sections
    )
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chunks = _split_chunks(full_text)
    n = len(chunks)

    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        logger.debug("Summarizing chunk %d/%d", i + 1, n)
        summary = _generate_content(client, _CHUNK_PROMPT + "\n\n# Section Text\n\n" + chunk)
        chunk_summaries.append(summary)

    reduce_input = "\n\n".join(
        f"## Section {i + 1} of {n}\n\n{summary}"
        for i, summary in enumerate(chunk_summaries)
    )
    logger.debug("Synthesizing %d chunk summaries into final profile", n)
    profile = _generate_content(client, _REDUCE_PROMPT + "\n\n# Per-Section Notes\n\n" + reduce_input)

    with open(profile_path, "w") as f:
        f.write(profile)
    logger.debug("Profile written to %s", profile_path)
    return profile

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
You are reading a section of a book. The text is organized under headings \
(formatted as "## Heading") that correspond to chapters, parts, prologues, or \
similar divisions. A heading ending in "(continued)" — e.g., \
"## Chapter 5 (continued)" — means this chunk begins mid-chapter because the \
previous chunk was cut off; treat the text following such a heading as a \
continuation of that chapter until a new heading appears. For each item you \
extract below, note the chapter (or equivalent heading) it comes from — this \
lets the final profile anchor information to specific chapters so a reader \
can easily locate it. If a portion of the text has no heading, omit the \
chapter reference for that portion.

Extract the following from this section only:
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

Throughout the profile, anchor your references to specific chapters (or equivalent \
divisions like prologues, parts, etc.) wherever the per-section notes provide that \
information. Chapter anchors let the assistant answer questions like "where was this \
character introduced?" or "which chapter does X happen in?". Omit chapter references \
only when the source material lacks chapter structure for that portion.

# Synopsis
A thorough overview of the full plot arc from beginning to end. Reference chapters \
as you narrate major movements of the plot.

# Characters
Key characters: their role, motivations, and relationships to one another. For each \
character, note the chapter in which they are introduced and any chapters containing \
notable developments. Include minor characters as well. Include as much detail as \
their role in the narrative warrants.

# Themes
Major themes and motifs explored throughout the book. Where a theme is particularly \
prominent in specific chapters, reference those chapters.

# Setting
Time period, locations, and world-building details relevant to understanding the story. \
Reference the chapter in which each location or world-building detail is introduced. \
You can draw from your own knowledge to fill in the gaps here. \
Only draw from your knowledge for verifiable historical or cultural context.

# Key Events
A chronological list of major plot beats and turning points, each annotated with the \
chapter it occurs in. Include details that a human reader would consider obvious but \
are necessary to understand character motivations, causal links, or narrative logic.
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


def _split_chunks(sections: list[Section]) -> list[str]:
    """
    Pack sections into chunks on clean chapter boundaries. A chunk only splits
    a section when that section alone exceeds _MAX_CHUNK_CHARS; in that case,
    continuation pieces get a "(continued)" header.
    """
    chunks: list[str] = []
    current = ""

    for s in sections:
        section_text = f"## {s.title}\n\n{s.text}" if s.title else s.text
        separator = "\n\n" if current else ""

        if len(current) + len(separator) + len(section_text) <= _MAX_CHUNK_CHARS:
            current += separator + section_text
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(section_text) <= _MAX_CHUNK_CHARS:
            current = section_text
            continue

        # Oversized section — must split. First slice keeps the original header;
        # subsequent slices get a "(continued)" header prepended.
        continued_header = f"## {s.title} (continued)\n\n" if s.title else ""
        chunks.append(section_text[:_MAX_CHUNK_CHARS])
        pos = _MAX_CHUNK_CHARS
        budget = _MAX_CHUNK_CHARS - len(continued_header)
        while pos < len(section_text):
            chunks.append(continued_header + section_text[pos : pos + budget])
            pos += budget

    if current:
        chunks.append(current)
    return chunks


def generate_profile(sections: list[Section]) -> str:
    logger.debug("Generating profile")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chunks = _split_chunks(sections)
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
    return _generate_content(client, _REDUCE_PROMPT + "\n\n# Per-Section Notes\n\n" + reduce_input)

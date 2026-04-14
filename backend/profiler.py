import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger("steinbot")

_PROFILE_PROMPT = """\
You are a literary analyst. Given the full text of a book, produce a structured \
reference document with the following five sections. Be thorough — this document \
will be used by an AI assistant to answer reader questions about the book.

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


def generate_profile(book_text: list[str], epub_path: str) -> str:
    profile_path = os.path.splitext(epub_path)[0] + ".profile.txt"

    if os.path.exists(profile_path):
        logger.debug("Profile already exists at %s — skipping generation", profile_path)
        with open(profile_path) as f:
            return f.read()

    logger.debug("Generating profile for %s", epub_path)
    full_text = "\n\n".join(book_text)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=_PROFILE_PROMPT + "\n\n# Book Text\n\n" + full_text)],
            )
        ],
    )

    profile = response.text
    with open(profile_path, "w") as f:
        f.write(profile)

    logger.debug("Profile written to %s", profile_path)
    return profile

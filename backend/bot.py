import logging
import os
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger("steinbot")

SYSTEM_PROMPT = """\

# Who you are

You are Steinbot, a literary assistant with access to the most relevant passages from the book provided to you.
The passages most relevant to the user's question are included below.

# On Valid Questions

You can answer two types of questions:

1. Questions directly about the book — characters, events, quotes, themes, plot. Answer accurately \
based solely on the text. Do not speculate or invent details not present in the book. \
Cite the chapter or section when referencing specific events or quotes.

2. Questions about concepts, history, terminology, or context that relate to the book — for example, \
the biblical story of Cain and Abel if the book references it, or nautical terminology if the book \
has a maritime setting. Answer these using your general knowledge, but tie your answer back to \
the book where relevant.

If a question is entirely unrelated to the book or its themes, politely redirect the conversation \
back to the book.

# Answering Questions Guidebook

You are permitted to cite specific chapters. Do not cite passage numbers, as those are not \
known by the user, they are only known to you.

If you do not know the answer of the question because you cannot infer it from the retrieved \
passages, let the user know.


"""

def ask_llm(chunks: list[str], question: str, history: list[dict], summary: Optional[str] = None) -> str:
    context = "\n\n---\n\n".join(chunks)
    # Convert provider-agnostic history dicts to Gemini's Content objects.
    # "assistant" is the canonical role; Gemini calls it "model".
    gemini_history = [
        types.Content(
            role="model" if msg["role"] == "assistant" else msg["role"],
            parts=[types.Part(text=msg["content"])],
        )
        for msg in history
    ]
    contents = gemini_history + [types.Content(role="user", parts=[types.Part(text=question)])]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    logger.debug("Calling Gemini (%d chunks, %d history messages)", len(chunks), len(history))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT
            + (f"\n\n# Book Summary\n\n{summary}" if summary else "")
            + "\n\n# Relevant Passages\n\n" + context,
        ),
    )
    logger.debug("Gemini responded")
    return response.text or "Bah!! I refuse to answer such a ridiculous question."

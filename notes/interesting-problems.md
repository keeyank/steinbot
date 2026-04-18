# Interesting Problems

## Problem 1: Factual accuracy on plot-critical questions

**The question:** "Did Cathy kill her parents?"

Steinbot was failing to answer this correctly — a question with a clear, verifiable answer in the
text that even frontier models (GPT-4, Claude) get right out of the box.

**Root cause:** Poor retrieval. The RAG pipeline wasn't surfacing the right passages. The chunks
being retrieved were too small and too sparse, so the model was answering with insufficient context.

**Solution:**

Two levers were pulled together:

1. **Better retrieval model** — switched to a stronger embedding model (`BAAI/bge-base-en-v1.5`)
   for encoding chunks and queries. Better embeddings = more semantically relevant chunks retrieved.

2. **Better retrieval parameters** — increased chunk size (`CHUNK_WORDS`), overlap between chunks
   (`OVERLAP_WORDS`), and the number of chunks passed to the model (`TOP_K`). This meant more of
   the book's relevant context was making it into the prompt.

The combined effect: the model now receives higher-quality, more complete context, and answers
correctly — on par with frontier models that have the full book in their context window.

**Takeaway:** In RAG systems, the model is often not the bottleneck. Bad retrieval starves the
model of the information it needs. Fixing retrieval quality and quantity can close a large gap
without changing the model at all.

## Problem 2: Generating a book profile when the book exceeds the rate limit

**The problem:** Generating a structured profile (synopsis, characters, themes, etc.) requires
sending the full book text to an LLM. Long books like Shogun are ~600k tokens. The Gemini free
tier caps input at 250k tokens/minute — so a single request fails with RESOURCE_EXHAUSTED.

**Solution: map-reduce summarization**

The idea comes from distributed computing. Instead of one giant request, split the work:

1. **Map** — divide the book into chunks (~50k tokens each) and send each chunk to the model
   independently with a focused extraction prompt: pull out characters, plot events, setting
   details, and themes from *this section only*.

2. **Reduce** — send all the chunk summaries together in one final request, asking the model to
   synthesize them into the full structured profile.

Each individual request is well within the rate limit. The model never sees the whole book at
once, but it sees everything — just in pieces, then synthesized.

**Why it works for profiling:** A book profile doesn't require holistic reading in a single pass.
Characters, events, and settings can be extracted locally from each section, then a second-pass
synthesis step connects the dots. The reduce prompt has a small, well-structured input (summaries)
rather than raw prose, which actually makes the final synthesis cleaner.

**Takeaway:** When a task is too large for one LLM call — whether due to context limits or rate
limits — map-reduce is the standard pattern. Break the input into independent pieces (map),
process each, then combine the results (reduce). It's the same idea that powers distributed
data processing at scale, just applied to prompts.

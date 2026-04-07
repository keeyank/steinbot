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

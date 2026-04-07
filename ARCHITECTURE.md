# Steinbot Architecture

## Tech Stack

| Layer | Library | Notes |
|-------|---------|-------|
| EPUB parsing | `ebooklib` + `beautifulsoup4` | Extracts plain text from EPUB HTML chapters |
| Chunking | Custom (`retriever.py`) | Pure Python, no dependencies |
| Embedding model | `sentence-transformers` — `all-MiniLM-L6-v2` | Runs locally, no API calls, no cost |
| Vector store | `ChromaDB` | Persisted to disk at `<epub-dir>/.cache/` |
| LLM | Google Gemini `gemini-2.5-flash-lite` via `google-genai` | API call, free tier |
| Config | `python-dotenv` | Loads `GEMINI_API_KEY` from `.env` |

---

## Indexing Pipeline (run once per book)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INDEXING PIPELINE                           │
│                     (first run only, then cached)                   │
└─────────────────────────────────────────────────────────────────────┘

  book.epub
      │
      ▼
  ebooklib + BeautifulSoup
  Extract text from all EPUB chapters, strip HTML
      │
      ▼
  Raw book text  (one large string)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    CHUNKING                             │
│                                                         │
│  1. Split on \n\n → paragraphs                          │
│  2. Flatten all paragraphs → word list                  │
│  3. Slide a window across the word list:                │
│                                                         │
│     [  chunk 1: 500 words  ]                            │
│                    [  chunk 2: 500 words  ]             │
│                                 [  chunk 3: 500 words ] │
│     ◄─ 450 words ─►                                     │
│                  (50-word overlap between chunks)       │
└─────────────────────────────────────────────────────────┘
      │
      │  list of ~500-word strings
      ▼
  SentenceTransformer ("all-MiniLM-L6-v2")
  Encode each chunk → 384-dimensional float vector
  Runs locally on CPU
      │
      │  (chunk_text, vector) pairs
      ▼
  ChromaDB  — persisted to <epub-dir>/.cache/
  Collection named after epub filename
  Stored on disk, loaded instantly on future runs
```

---

## Query Pipeline (every question)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          QUERY PIPELINE                             │
└─────────────────────────────────────────────────────────────────────┘

  User types a question
      │
      ▼
  SentenceTransformer ("all-MiniLM-L6-v2")
  Encode question → 384-dimensional float vector
      │
      ▼
  ChromaDB cosine similarity search
  Returns top 5 chunks whose vectors are closest
  to the question vector
      │
      │  5 x ~500-word passage strings
      ▼
┌─────────────────────────────────────────────────────┐
│                  PROMPT ASSEMBLY                    │
│                                                     │
│  System prompt (Steinbot persona + instructions)    │
│  +                                                  │
│  # Relevant Passages                                │
│  <chunk 1>                                          │
│  ---                                                │
│  <chunk 2>                                          │
│  ---                                                │
│  ...                                                │
└─────────────────────────────────────────────────────┘
      │
      ▼
  Gemini API  (gemini-2.5-flash-lite)
  Generate answer grounded in retrieved passages
      │
      ▼
  Response printed to terminal
```

---

## Cache Strategy

The ChromaDB index is keyed by epub filename and stored at `<epub-dir>/.cache/<collection-name>/`. On startup, `build_index()` checks if the collection already exists — if so, it returns immediately. Re-indexing only happens if the cache directory is deleted or a new epub is used.

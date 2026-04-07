# Future Updates

- [ ] File upload is broken and needs to be fixed
- [ ] Restrict CORS to frontend domain before deploying
- [ ] Support PDF format
- [ ] Persist conversation history per user (requires auth + database)
- [ ] Display nicer book names

## Book Identity and Storage

Currently the uploaded filename doubles as the book's unique ID. This breaks with filenames that have spaces, special characters, or collide with an existing upload.

**Better approach:** assign a UUID on upload (`str(uuid.uuid4())`), save the file as `{uuid}.epub`, and store the original filename separately as the display name. UUIDs require no persistent state and are already used for session IDs.

The catch: once ID and filename are decoupled, the display name has to live somewhere. Right now `GET /books` derives names by scanning filenames on disk — that no longer works. This is the natural forcing function for introducing a lightweight database (SQLite would be enough), with a `books` table: `(id TEXT, filename TEXT, display_name TEXT)`.

**When to implement:** when the filename-collision problem actually bites, or when the database is added for conversation history persistence (see below).

# Future Considerations

## Auto-generated Book Summaries

Currently summaries must be manually written and dropped in as `<book>.summary.txt`. This should be automated.

**Proposed approach:** when a book is uploaded for the first time, auto-generate a detailed summary
using the LLM. Two possible strategies:
- For well-known books, simply prompt the model to produce a thorough plot and character summary
  from its training knowledge (fast, no token cost from the book itself)
- For unknown/obscure books, generate the summary from the full text or a large sample of it

The summary should cover major plot threads, character arcs, and causal connections — especially
non-obvious links (e.g. character A from act 1 reappears as character B in act 2) that retrieval
alone won't surface.

**When to implement:** once the upload flow exists and summary files become a maintenance burden.

## Re-ranking

If retrieval accuracy hits a ceiling that better bi-encoder models and parameter tuning can't fix,
consider adding a cross-encoder re-ranker as a second retrieval stage.

**How it would work:** bi-encoder retrieves top ~50 candidates (fast), re-ranker scores each
(query, passage) pair together and re-orders them, top K go to the LLM. More accurate but slower.

**When to revisit:** if there are questions where the right passage is clearly in the book but
Steinbot still gets the answer wrong, and tuning CHUNK_WORDS / OVERLAP_WORDS / TOP_K doesn't help.

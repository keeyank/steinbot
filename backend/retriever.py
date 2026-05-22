import logging

import chromadb
from sentence_transformers import SentenceTransformer

from parser import Section

logger = logging.getLogger("steinbot")

# Index Build Params - if you change these (or the chunk metadata schema below),
# delete the .index directory to trigger a rebuild.
CHUNK_WORDS = 750
OVERLAP_WORDS = 100

# Query Params - Used on every query
TOP_K = 12

_model = None

def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _model


def _chunk_text(sections: list[Section], chunk_words: int = CHUNK_WORDS, overlap_words: int = OVERLAP_WORDS) -> list[dict]:
    logger.debug("Chunking %d sections", len(sections))
    chunks = []
    global_index = 0
    for section_index, section in enumerate(sections):
        words = section.text.split()
        start = 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            chunks.append({
                "text": " ".join(words[start:end]),
                "chunk_index": global_index,
                "word_count": len(words[start:end]),
                "section_index": section_index,
                "section_title": section.title or "",
            })
            global_index += 1
            if end == len(words):
                break
            start += chunk_words - overlap_words
    logger.debug("Chunked into %d chunks", len(chunks))
    return chunks


def load_or_build_index(sections: list[Section], *, index_dir: str, collection_name: str) -> None:
    client = chromadb.PersistentClient(path=index_dir)

    existing = [c.name for c in client.list_collections()]
    if collection_name in existing:
        logger.debug("Index already exists for '%s', skipping build", collection_name)
        return

    logger.debug("Building index for '%s'", collection_name)
    chunks = _chunk_text(sections)
    texts = [c["text"] for c in chunks]
    metadatas = [
        {
            "chunk_index": c["chunk_index"],
            "word_count": c["word_count"],
            "section_index": c["section_index"],
            "section_title": c["section_title"],
        }
        for c in chunks
    ]

    model = _get_model()
    logger.debug("Encoding %d chunks", len(chunks))
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    logger.debug("Writing index to ChromaDB")
    collection = client.create_collection(collection_name)
    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.debug("Index built — %d chunks stored", len(chunks))


def drop_index(*, index_dir: str, collection_name: str) -> None:
    client = chromadb.PersistentClient(path=index_dir)
    if any(c.name == collection_name for c in client.list_collections()):
        client.delete_collection(collection_name)
        logger.debug("Dropped collection '%s'", collection_name)


def get_relevant_chunks(question: str, *, index_dir: str, collection_name: str, k: int = TOP_K) -> list[str]:
    client = chromadb.PersistentClient(path=index_dir)
    collection = client.get_collection(collection_name)

    model = _get_model()
    logger.debug("Encoding question for retrieval")
    query_embedding = model.encode([question]).tolist()

    logger.debug("Querying index for top %d chunks", k)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(k, collection.count()),
        include=["documents", "metadatas"],
    )
    logger.debug("Retrieved %d chunks", len(results["documents"][0]))

    formatted = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        title = meta["section_title"] or "untitled"
        prefix = f'[Section {meta["section_index"]}: "{title}", passage {meta["chunk_index"]}, {meta["word_count"]} words]'
        formatted.append(f"{prefix}\n{doc}")
    return formatted

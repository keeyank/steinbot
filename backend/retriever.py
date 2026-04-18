import logging
import os

import chromadb
from sentence_transformers import SentenceTransformer

from parser import Section

logger = logging.getLogger("steinbot")

# Index Build Params - if you change these (or the chunk metadata schema below),
# delete uploads/.index to trigger a rebuild.
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


def _collection_name(epub_path: str) -> str:
    return os.path.splitext(os.path.basename(epub_path))[0].replace(" ", "_")


def _get_client(epub_path: str) -> chromadb.PersistentClient:
    index_dir = os.path.join(os.path.dirname(os.path.abspath(epub_path)), ".index")
    return chromadb.PersistentClient(path=index_dir)


def load_or_build_index(sections: list[Section], epub_path: str) -> None:
    client = _get_client(epub_path)
    name = _collection_name(epub_path)

    existing = [c.name for c in client.list_collections()]
    if name in existing:
        logger.debug("Index already exists for '%s', skipping build", name)
        return

    logger.debug("Building index for '%s'", name)
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
    collection = client.create_collection(name)
    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.debug("Index built — %d chunks stored", len(chunks))


def get_relevant_chunks(question: str, epub_path: str, k: int = TOP_K) -> list[str]:
    client = _get_client(epub_path)
    name = _collection_name(epub_path)
    collection = client.get_collection(name)

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

import logging
import os
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot import ask_llm
from db import DATA_DIR, Book, get_db, init_db
from parser import Section, parse_epub
from profiler import generate_profile
from retriever import drop_index, get_relevant_chunks, load_or_build_index

INDEX_DIR = os.path.join(DATA_DIR, ".index")

app = FastAPI()

# TODO: restrict to frontend domain before deploying (see FUTURE.md)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging — one file per server run, also output to console
os.makedirs("logs", exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("steinbot")
logger.setLevel(logging.DEBUG)
_file_handler = logging.FileHandler(f"logs/{timestamp}_api.log")
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

init_db()

# Session store
# sessions[session_id] = { "current_book_id": int | None, "history": list[dict], "profile": str | None }
sessions: dict[str, dict] = {}


def _collection_name(book_id: int) -> str:
    return f"book_{book_id}"


def _epub_path(book_id: int) -> str:
    return os.path.join(DATA_DIR, f"{book_id}.epub")


def _cleanup_failed_upload(book_id: int) -> None:
    """Best-effort cleanup of artifacts from a failed upload. Each step is isolated
    so a cleanup failure can't mask the original exception."""
    path = _epub_path(book_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        logger.exception("Failed to delete %s during cleanup", path)
    try:
        drop_index(index_dir=INDEX_DIR, collection_name=_collection_name(book_id))
    except Exception:
        logger.exception("Failed to drop index for book %d during cleanup", book_id)


@app.post("/session")
def create_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"current_book_id": None, "history": [], "profile": None}
    return {"session_id": session_id}


@app.get("/books")
def list_books(db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.created_at.desc())).all()
    return {"books": [{"id": b.id, "title": b.title} for b in books]}


@app.post("/session/{session_id}/book")
async def upload_book(session_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename.endswith(".epub") or file.filename.endswith(".epub.zip")):
        raise HTTPException(status_code=400, detail="Only .epub files are supported")

    save_name = file.filename.removesuffix(".zip")
    title = os.path.splitext(save_name)[0]

    book = Book(title=title)
    db.add(book)
    db.flush()  # populate book.id without committing

    epub_path = _epub_path(book.id)
    try:
        with open(epub_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)

        logger.info("Uploaded book %d (%s) — parsing, indexing, profiling", book.id, title)
        sections: list[Section] = parse_epub(epub_path)
        load_or_build_index(sections, index_dir=INDEX_DIR, collection_name=_collection_name(book.id))
        book.profile = generate_profile(sections)
        db.commit()
        logger.debug("Indexed and profiled book %d", book.id)
    except Exception:
        _cleanup_failed_upload(book.id)
        raise

    return {"book_id": book.id}


class AskRequest(BaseModel):
    session_id: str
    book_id: int
    question: str


@app.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    book = db.get(Book, req.book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {req.book_id} not found")

    logger.debug("[%s] Question: %s", req.session_id[:8], req.question)

    if req.book_id != session["current_book_id"]:
        logger.debug("Book switched to %d", req.book_id)
        session["current_book_id"] = req.book_id
        session["history"] = []
        session["profile"] = book.profile

    chunks = get_relevant_chunks(
        req.question,
        index_dir=INDEX_DIR,
        collection_name=_collection_name(req.book_id),
    )
    answer = ask_llm(chunks, req.question, session["history"], session["profile"])

    logger.debug("[%s] Done", req.session_id[:8])

    session["history"].append({"role": "user", "content": req.question})
    session["history"].append({"role": "assistant", "content": answer})

    return {"answer": answer}

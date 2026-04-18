import logging
import os
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot import ask_llm
from parser import Section, parse_epub
from profiler import generate_profile
from retriever import load_or_build_index, get_relevant_chunks

app = FastAPI()

# TODO: restrict to frontend domain before deploying (see FUTURE.md)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

# Session store
# sessions[session_id] = { "current_book_id": str | None, "history": list[dict] }
sessions: dict[str, dict] = {}


@app.post("/session")
def create_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"current_book_id": None, "history": []}
    return {"session_id": session_id}


@app.get("/books")
def list_books():
    books = []
    for filename in os.listdir(UPLOAD_DIR):
        if filename.endswith(".epub"):
            # Todo: Pull book name from DB
            name = os.path.splitext(filename)[0].replace("-", " ")
            books.append({"id": filename, "name": name})
    return {"books": books}


@app.post("/session/{session_id}/book")
async def upload_book(session_id: str, file: UploadFile = File(...)):
    if not (file.filename.endswith(".epub") or file.filename.endswith(".epub.zip")):
        raise HTTPException(status_code=400, detail="Only .epub files are supported")

    # Always save as .epub regardless of whether the browser appended .zip
    save_name = file.filename.removesuffix(".zip")
    save_path = os.path.join(UPLOAD_DIR, save_name)
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    book_id = save_name
    logger.info("Uploaded %s — parsing, indexing, and profiling", book_id)
    sections: list[Section] = parse_epub(save_path)
    load_or_build_index(sections, save_path)
    generate_profile(sections, save_path)
    logger.debug("Indexed and profiled %s", book_id)

    return {"book_id": book_id}


class AskRequest(BaseModel):
    session_id: str
    book_id: str
    question: str


@app.post("/ask")
def ask(req: AskRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    epub_path = os.path.join(UPLOAD_DIR, req.book_id)
    if not os.path.exists(epub_path):
        raise HTTPException(status_code=400, detail=f"Book '{req.book_id}' not found")

    logger.debug("[%s] Question: %s", req.session_id[:8], req.question)

    if req.book_id != session["current_book_id"]:
        logger.debug("Book switched to %s", req.book_id)
        session["current_book_id"] = req.book_id
        session["history"] = []

        profile_path = os.path.splitext(epub_path)[0] + ".profile.txt"
        if os.path.exists(profile_path):
            with open(profile_path) as f:
                session["profile"] = f.read()
            logger.debug("Loaded profile from %s", profile_path)
        else:
            session["profile"] = None

    chunks = get_relevant_chunks(req.question, epub_path)
    answer = ask_llm(chunks, req.question, session["history"], session.get("profile"))

    logger.debug("[%s] Done", req.session_id[:8])

    session["history"].append({"role": "user", "content": req.question})
    session["history"].append({"role": "assistant", "content": answer})

    return {"answer": answer}

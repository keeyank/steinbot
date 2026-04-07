import logging
import os
import sys
from datetime import datetime
from parser import parse_epub
from retriever import load_or_build_index, get_relevant_chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path-to-epub>")
        sys.exit(1)

    epub_path = sys.argv[1]
    if not os.path.exists(epub_path):
        print(f"File not found: {epub_path}")
        sys.exit(1)

    print(f"Parsing {epub_path}...")
    book_text = parse_epub(epub_path)
    print(f"Loaded {sum(len(c) for c in book_text):,} characters.")
    load_or_build_index(book_text, epub_path)

    summary_path = os.path.splitext(epub_path)[0] + ".summary.txt"
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = f.read()
        print(f"Loaded summary from {summary_path}")
    else:
        summary = None

    book_name = os.path.splitext(os.path.basename(epub_path))[0]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/{timestamp}_{book_name}.log"
    logger = logging.getLogger("steinbot")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    from bot import ask_llm

    history = []
    print("Steinbot is ready. Ask anything about the book. Type 'quit' to exit.\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        chunks = get_relevant_chunks(question, epub_path)
        print("Steinbot: ", end="", flush=True)
        answer = ask_llm(chunks, question, history, summary)
        print(answer)
        print()

        logger.debug("QUESTION: %s", question)
        logger.debug("RETRIEVED PASSAGES:\n%s", "\n---\n".join(chunks))
        logger.debug("ANSWER: %s", answer)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()

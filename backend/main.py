import logging
import os
import sys
from datetime import datetime
from parser import Section, parse_epub
from profiler import generate_profile
from retriever import get_relevant_chunks, load_or_build_index


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path-to-epub>")
        sys.exit(1)

    epub_path = sys.argv[1]
    if not os.path.exists(epub_path):
        print(f"File not found: {epub_path}")
        sys.exit(1)

    print(f"Parsing {epub_path}...")
    sections: list[Section] = parse_epub(epub_path)
    print(f"Loaded {sum(len(s.text) for s in sections):,} characters across {len(sections)} sections.")

    index_dir = os.path.join(os.path.dirname(os.path.abspath(epub_path)), ".index")
    collection_name = os.path.splitext(os.path.basename(epub_path))[0].replace(" ", "_")
    load_or_build_index(sections, index_dir=index_dir, collection_name=collection_name)

    profile_path = os.path.splitext(epub_path)[0] + ".profile.txt"
    if os.path.exists(profile_path):
        with open(profile_path) as f:
            profile = f.read()
        print(f"Loaded profile from {profile_path}")
    else:
        print("Generating profile...")
        profile = generate_profile(sections)
        with open(profile_path, "w") as f:
            f.write(profile)
        print(f"Wrote profile to {profile_path}")

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

        chunks = get_relevant_chunks(question, index_dir=index_dir, collection_name=collection_name)
        print("Steinbot: ", end="", flush=True)
        answer = ask_llm(chunks, question, history, profile)
        print(answer)
        print()

        logger.debug("QUESTION: %s", question)
        logger.debug("RETRIEVED PASSAGES:\n%s", "\n---\n".join(chunks))
        logger.debug("ANSWER: %s", answer)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Count characters in an EPUB file."""
import sys
from parser import parse_epub


def count_chars(filepath: str) -> int:
    chapters = parse_epub(filepath)
    return sum(len(chapter) for chapter in chapters)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 count_chars.py <path_to_epub>")
        sys.exit(1)

    path = sys.argv[1]
    total = count_chars(path)
    print(f"Character count: {total:,}")

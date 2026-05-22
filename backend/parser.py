import io
import re
import zipfile
from dataclasses import dataclass

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Section:
    title: str | None
    text: str


_TITLE_PATTERN = re.compile(
    r"^\s*(prologue|epilogue|chapter\s+\S+|part\s+\S+|book\s+\S+|introduction|foreword|afterword|preface)\b",
    re.IGNORECASE,
)


def _strip_zip_prefix(filepath: str) -> None:
    """
    Some epub zips have all entries nested under a top-level directory
    (e.g. Shōgun.epub/META-INF/... instead of META-INF/...).
    Repack in place to remove the prefix so ebooklib can read it.
    """
    with zipfile.ZipFile(filepath) as zf:
        tops = {n.split("/")[0] for n in zf.namelist() if n}
        if len(tops) != 1:
            return
        prefix = tops.pop() + "/"
        if f"{prefix}META-INF/container.xml" not in zf.namelist():
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for item in zf.infolist():
                stripped = item.filename[len(prefix):]
                if stripped and not stripped.endswith("/"):
                    out.writestr(stripped, zf.read(item.filename))
    with open(filepath, "wb") as f:
        f.write(buf.getvalue())


def _extract_title(soup: BeautifulSoup, text: str) -> str | None:
    # Preferred: well-formed EPUBs put the chapter title in an <h1> or <h2> tag.
    for tag_name in ("h1", "h2"):
        heading = soup.find(tag_name)
        if heading:
            heading_text = heading.get_text(strip=True)
            if heading_text:
                return heading_text

    # Fallback: no heading tag, so treat the document as titled only if its
    # first non-empty line itself looks like "Chapter X" / "Prologue" / etc.
    # We deliberately stop at the first non-empty line — if the doc doesn't
    # *start* with a heading-shaped line, it isn't a titled section.
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = _TITLE_PATTERN.match(line)
        if match:
            return match.group(0).strip()
        return None
    return None


def parse_epub(filepath: str) -> list[Section]:
    _strip_zip_prefix(filepath)
    book = epub.read_epub(filepath)
    sections: list[Section] = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        if text:
            title = _extract_title(soup, text)
            sections.append(Section(title=title, text=text))

    return sections

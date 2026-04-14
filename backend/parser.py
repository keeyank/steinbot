import io
import zipfile

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


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


def parse_epub(filepath: str) -> list[str]:
    _strip_zip_prefix(filepath)
    book = epub.read_epub(filepath)
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        if text:
            chapters.append(text)

    return chapters

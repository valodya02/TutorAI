import json
import re
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books"
BOOKS.mkdir(parents=True, exist_ok=True)

DEFAULT_PATTERN = r"^(?P<title>.+?)[\s.·…]{2,}(?P<page>\d+)\s*$"

router = APIRouter(prefix="/api/books")


# ---------- файлы ----------

def book_dir(book_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", book_id):
        raise HTTPException(404, "Учебник не найден")
    d = BOOKS / book_id
    if not d.exists():
        raise HTTPException(404, "Учебник не найден")
    return d


def read_book(book_id: str) -> dict:
    return json.loads((book_dir(book_id) / "book.json").read_text(encoding="utf-8"))


def write_book(d: Path, data: dict) -> None:
    (d / "book.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- оглавление ----------

def add_ranges(entries: list[dict], n_pages: int) -> list[dict]:
    """Диапазон раздела: от его страницы до страницы перед следующим разделом
    того же или более высокого уровня. Страницы нумеруются с 1 (как в PDF)."""
    for i, e in enumerate(entries):
        end = n_pages
        for nxt in entries[i + 1:]:
            if nxt["level"] <= e["level"]:
                end = max(e["page_start"], nxt["page_start"] - 1)
                break
        e["page_end"] = min(end, n_pages)
    return entries


def toc_from_bookmarks(doc) -> list[dict]:
    entries = []
    for level, title, page in doc.get_toc():
        if page < 1:  # закладка без страницы
            continue
        entries.append({"title": title.strip(), "level": level, "page_start": page})
    return add_ranges(entries, doc.page_count)


def parse_page_range(s: str, n_pages: int) -> list[int]:
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", s or "")
    if not m:
        raise HTTPException(400, "Страницы оглавления: например 5-8")
    a = int(m.group(1))
    b = int(m.group(2) or a)
    if not (1 <= a <= b <= n_pages):
        raise HTTPException(400, "Страницы оглавления вне документа")
    return list(range(a - 1, b))


def toc_from_text(doc, toc_pages: str, offset: int, pattern: str) -> list[dict]:
    """offset: pdf_page = напечатанная_страница + offset."""
    try:
        rx = re.compile(pattern)
    except re.error as e:
        raise HTTPException(400, f"Неверный шаблон: {e}")
    if not {"title", "page"} <= set(rx.groupindex):
        raise HTTPException(400, "В шаблоне нужны группы (?P<title>...) и (?P<page>...)")
    entries = []
    for p in parse_page_range(toc_pages, doc.page_count):
        prev = ""
        for line in doc[p].get_text("text").splitlines():
            line = line.strip()
            m = rx.match(line)
            if not m and prev and re.fullmatch(r"\d+", line):
                m = rx.match(f"{prev} .. {line}")  # номер страницы на отдельной строке
            if not m:
                prev = line
                continue
            prev = ""
            title = m.group("title").strip()
            page = int(m.group("page")) + offset
            if not (1 <= page <= doc.page_count):
                continue
            num = re.match(r"^(\d+(?:\.\d+)*)\.?\s", title)
            level = num.group(1).count(".") + 1 if num else 1
            entries.append({"title": title, "level": level, "page_start": page})
    return add_ranges(entries, doc.page_count)


# ---------- API ----------

class TocSettings(BaseModel):
    toc_pages: str
    offset: int = 0
    pattern: str = DEFAULT_PATTERN


def summary(b: dict) -> dict:
    return {k: b[k] for k in ("id", "title", "pages", "source", "sections")}


@router.post("")
def upload_book(file: UploadFile, title: str = Form("")):
    data = file.file.read()
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise HTTPException(400, "Не удалось открыть PDF")
    if not any(doc[i].get_text("text").strip() for i in range(min(doc.page_count, 10))):
        raise HTTPException(400, "В PDF нет текстового слоя (скан). Нужен OCR.")

    book_id = uuid.uuid4().hex[:8]
    d = BOOKS / book_id
    (d / "sections").mkdir(parents=True)
    (d / "book.pdf").write_bytes(data)

    toc = toc_from_bookmarks(doc)
    book = {
        "id": book_id,
        "title": title.strip() or (file.filename or "Учебник").removesuffix(".pdf"),
        "pages": doc.page_count,
        "source": "bookmarks" if toc else "none",
        "sections": len(toc),
        "toc": toc,
    }
    write_book(d, book)
    # source == "none": закладок нет, нужен POST /{id}/toc с настройками
    return summary(book)


@router.post("/{book_id}/toc")
def reparse_toc(book_id: str, s: TocSettings):
    d = book_dir(book_id)
    book = read_book(book_id)
    doc = fitz.open(d / "book.pdf")
    toc = toc_from_text(doc, s.toc_pages, s.offset, s.pattern)
    if not toc:
        raise HTTPException(422, "По этим настройкам не найдено ни одной строки оглавления")
    for f in (d / "sections").glob("*.txt"):  # кэш привязан к старым номерам
        f.unlink()
    book.update(toc=toc, sections=len(toc), source="manual", settings=s.model_dump())
    write_book(d, book)
    return summary(book)


@router.get("")
def list_books():
    result = []
    for d in sorted(BOOKS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        f = d / "book.json"
        if f.exists():
            result.append(summary(json.loads(f.read_text(encoding="utf-8"))))
    return result


@router.get("/{book_id}")
def get_book(book_id: str):
    return read_book(book_id)


@router.get("/{book_id}/pages/{p}")
def get_page(book_id: str, p: int):
    """Сырой текст страницы PDF (с 1), чтобы подобрать шаблон оглавления."""
    doc = fitz.open(book_dir(book_id) / "book.pdf")
    if not (1 <= p <= doc.page_count):
        raise HTTPException(404, "Нет такой страницы")
    return {"page": p, "text": doc[p - 1].get_text("text")}


@router.get("/{book_id}/sections/{n}")
def get_section(book_id: str, n: int):
    d = book_dir(book_id)
    book = read_book(book_id)
    if not (0 <= n < len(book["toc"])):
        raise HTTPException(404, "Раздел не найден")
    sec = book["toc"][n]
    cache = d / "sections" / f"{n}.txt"
    if cache.exists():
        text = cache.read_text(encoding="utf-8")
    else:
        doc = fitz.open(d / "book.pdf")
        pages = range(sec["page_start"] - 1, sec["page_end"])
        text = "\n\n".join(doc[p].get_text("text").strip() for p in pages)
        cache.write_text(text, encoding="utf-8")
    return {
        **sec,
        "text": text,
        "chars": len(text),
        "tokens_estimate": len(text) // 3,  # грубо, для кириллицы
    }
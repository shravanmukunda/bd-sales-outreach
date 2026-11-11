"""Load Webknot source files. Web pages and docs are tagged so chunking can differ."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from webknot_bd.config import settings


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Read a tiny `---` block. Values stay strings; callers coerce booleans."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _base_metadata(path: Path, doc_type: str, meta: dict[str, str]) -> dict[str, object]:
    return {
        "source": path.name,
        "doc_type": doc_type,
        "industry": meta.get("industry", "general") or "general",
        "service": meta.get("service", "general") or "general",
        "sample": as_bool(meta.get("sample", False)),
    }


def load_text_file(path: Path, doc_type: str) -> Document:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Document(page_content=body, metadata=_base_metadata(path, doc_type, meta))


def load_pdf(path: Path, doc_type: str) -> list[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    pages = PyPDFLoader(str(path)).load()
    metadata = _base_metadata(path, doc_type, {})
    for page in pages:
        page.metadata.update(metadata)
    return pages


def load_dir(folder: Path, doc_type: str) -> list[Document]:
    if not folder.exists():
        return []
    documents: list[Document] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            documents.append(load_text_file(path, doc_type))
        elif suffix == ".pdf":
            documents.extend(load_pdf(path, doc_type))
    return documents


def load_raw(root: Path | None = None) -> list[Document]:
    """Load `web/` for recursive chunking and `docs/` for fixed-size chunking."""
    root = root or settings.data_raw
    return load_dir(root / "web", "web") + load_dir(root / "docs", "doc")

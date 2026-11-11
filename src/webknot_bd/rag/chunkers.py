"""Two chunking strategies: recursive for web pages, fixed-size for internal docs."""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

from webknot_bd.config import settings


def chunk_web(documents: list[Document]) -> list[Document]:
    """Recursive splitting on headings, paragraphs, then words. Used for web content."""
    if not documents:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.web_chunk_size,
        chunk_overlap=settings.web_chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["chunk_strategy"] = "recursive"
    return chunks


def chunk_docs(documents: list[Document]) -> list[Document]:
    """Fixed-size character windows. Used for the ICP and other internal docs."""
    if not documents:
        return []
    splitter = CharacterTextSplitter(
        separator="",
        chunk_size=settings.doc_chunk_size,
        chunk_overlap=settings.doc_chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["chunk_strategy"] = "fixed"
    return chunks


def chunk_all(documents: list[Document]) -> list[Document]:
    web = [doc for doc in documents if doc.metadata.get("doc_type") == "web"]
    docs = [doc for doc in documents if doc.metadata.get("doc_type") != "web"]
    return chunk_web(web) + chunk_docs(docs)

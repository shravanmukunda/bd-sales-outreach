"""Build the persistent Chroma store from data/raw."""

from __future__ import annotations

import shutil

from webknot_bd.config import PROJECT_ROOT, logger, settings
from webknot_bd.rag.chunkers import chunk_all
from webknot_bd.rag.loaders import load_raw
from webknot_bd.rag.retriever import COLLECTION_NAME


def _wipe_store() -> None:
    directory = settings.chroma_dir.resolve()
    root = PROJECT_ROOT.resolve()
    if directory != root and root not in directory.parents:
        raise RuntimeError(f"Refusing to delete a Chroma directory outside the project: {directory}")
    if directory.exists():
        shutil.rmtree(directory)


def ingest() -> int:
    documents = load_raw()
    if not documents:
        raise FileNotFoundError(f"No documents found in {settings.data_raw}")
    chunks = chunk_all(documents)
    _wipe_store()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    Chroma.from_documents(
        documents=chunks,
        embedding=OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        ),
        collection_name=COLLECTION_NAME,
        persist_directory=str(settings.chroma_dir),
    )
    logger.info("Ingested %s chunks into %s", len(chunks), settings.chroma_dir)
    return len(chunks)

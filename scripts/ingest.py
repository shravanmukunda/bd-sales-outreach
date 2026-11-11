"""Load data/raw into the local Chroma store. Requires Ollama and nomic-embed-text."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webknot_bd.config import configure_logging
from webknot_bd.rag.ingest import ingest


def main() -> None:
    configure_logging()
    count = ingest()
    print(f"Ingested {count} chunks")


if __name__ == "__main__":
    main()

"""Chunking strategies and metadata filters. No vector store and no model."""

from langchain_core.documents import Document

from webknot_bd.rag.chunkers import chunk_all, chunk_docs, chunk_web
from webknot_bd.rag.loaders import load_raw
from webknot_bd.rag.rerank import parse_index_order
from webknot_bd.rag.retriever import build_filter, detect_industry


def test_fixed_size_chunks_stay_within_the_window():
    document = Document(
        page_content="B" * 2500,
        metadata={"source": "icp.md", "doc_type": "doc", "industry": "general", "service": "general", "sample": True},
    )
    chunks = chunk_docs([document])
    assert len(chunks) >= 2
    assert all(chunk.metadata["chunk_strategy"] == "fixed" for chunk in chunks)
    assert all(len(chunk.page_content) <= 1000 for chunk in chunks)


def test_recursive_chunks_are_marked():
    paragraph = "Dispatch software for a logistics team that needs a React board.\n\n"
    document = Document(
        page_content=paragraph * 40,
        metadata={"source": "services.md", "doc_type": "web", "industry": "logistics", "service": "product engineering", "sample": True},
    )
    chunks = chunk_web([document])
    assert len(chunks) >= 2
    assert all(chunk.metadata["chunk_strategy"] == "recursive" for chunk in chunks)


def test_seed_files_select_strategy_by_folder():
    documents = load_raw()
    by_source = {document.metadata["source"]: document for document in documents}
    assert by_source["icp.md"].metadata["doc_type"] == "doc"
    assert by_source["case_study_logistics.md"].metadata["industry"] == "logistics"
    assert by_source["case_study_logistics.md"].metadata["sample"] is True
    strategies = {}
    for chunk in chunk_all(documents):
        strategies[chunk.metadata["source"]] = chunk.metadata["chunk_strategy"]
    assert strategies["icp.md"] == "fixed"
    assert strategies["services.md"] == "recursive"
    assert strategies["case_study_logistics.md"] == "recursive"


def test_metadata_filter_and_rerank_parser():
    assert detect_industry("Which Webknot case study fits a logistics company?") == "logistics"
    assert build_filter("logistics", None) == {"industry": "logistics"}
    assert build_filter("logistics", "product engineering") == {
        "$and": [{"industry": "logistics"}, {"service": "product engineering"}]
    }
    assert parse_index_order("Most useful first: [2, 0, 1]", 3) == [2, 0, 1]
    assert parse_index_order("[0, 0, 1]", 3) is None

"""Vector store construction and RAG helper functions.

This module handles the ChromaDB vector store used for Retrieval-Augmented
Generation (RAG).  Each cloud provider (AWS, Azure) has its own ChromaDB
collection containing pre-embedded official documentation.  Domain validators
use the ``rag_search_function`` to retrieve relevant documentation snippets
that are injected into validation prompts for fact-checking.

When re-ranking is enabled, the initial retrieval fetches a larger candidate
set and then uses a FlashRank cross-encoder to rescore documents for higher
relevance accuracy before returning the top results.

The embedding model (Ollama-based ``nomic-embed-text``) must be running locally
for vector store queries to work.  The ChromaDB data is persisted on disk in
the directories specified by ``AppSettings.providers_aws_vector_path`` and
``providers_azure_vector_path``.
"""

from __future__ import annotations

import logging

from langchain_chroma import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings

from cloudy_intell.config.settings import AppSettings

logger = logging.getLogger(__name__)

_reranker_cache: dict[str, object] = {}


def _get_reranker(model_name: str):
    """Return a cached FlashRank Ranker instance (lazy-loaded)."""
    if model_name not in _reranker_cache:
        from flashrank import Ranker

        _reranker_cache[model_name] = Ranker(model_name=model_name)
    return _reranker_cache[model_name]


def create_vector_store(settings: AppSettings, provider: str = "aws") -> Chroma:
    """Create a cloud-documentation vector store instance.

    The path and collection name are resolved from provider-scoped settings so
    AWS and Azure can each have their own knowledge base.
    """

    embeddings = OllamaEmbeddings(model=settings.embedding_model)
    return Chroma(
        collection_name=settings.collection_name_for(provider),
        persist_directory=settings.vector_path_for(provider),
        embedding_function=embeddings,
    )


def rag_search_function(
    query: str,
    vector_store: Chroma,
    k: int = 5,
    *,
    rerank: bool = False,
    rerank_model: str = "ms-marco-MiniLM-L-12-v2",
    candidate_multiplier: int = 4,
) -> str:
    """Search vector store with optional cross-encoder re-ranking.

    When ``rerank`` is enabled the function fetches ``k * candidate_multiplier``
    candidates via embedding similarity, then uses a FlashRank cross-encoder to
    rescore them and keeps only the top ``k``.  This produces significantly more
    relevant results for complex cloud architecture queries.

    Args:
        query: Natural language query to search for.
        vector_store: ChromaDB instance to search against.
        k: Number of final documents to return.
        rerank: Whether to apply FlashRank cross-encoder re-ranking.
        rerank_model: FlashRank model name (only used when ``rerank=True``).
        candidate_multiplier: Fetch ``k * candidate_multiplier`` initial
            candidates before re-ranking.

    Returns:
        Formatted string of numbered document snippets separated by ``---``,
        or an error message if the search fails.
    """

    try:
        fetch_k = k * candidate_multiplier if rerank else k
        similar_docs = vector_store.similarity_search(query, k=fetch_k)
        if not similar_docs:
            return "No relevant documentation found in the vector database."

        if rerank:
            similar_docs = _rerank_documents(query, similar_docs, rerank_model, k)

        results = []
        max_snippet_length = 1000
        for i, doc in enumerate(similar_docs, 1):
            content = doc.page_content.strip()
            if len(content) > max_snippet_length:
                content = content[:max_snippet_length] + "... [truncated]"
            results.append(f"[Document {i}]:\n{content}\n")

        return "\n---\n".join(results)
    except Exception as exc:
        return f"Error searching vector database: {exc}"


def _rerank_documents(query: str, docs, model_name: str, top_k: int):
    """Re-rank documents using a FlashRank cross-encoder.

    Converts LangChain Document objects to FlashRank passages, scores them,
    and returns the top-k as LangChain Documents preserving original metadata.
    """

    from flashrank import RerankRequest

    ranker = _get_reranker(model_name)

    # Build passage dicts that FlashRank expects.
    passages = [{"id": i, "text": doc.page_content} for i, doc in enumerate(docs)]

    rerank_request = RerankRequest(query=query, passages=passages)
    ranked_results = ranker.rerank(rerank_request)

    # Map ranked results back to original LangChain Documents.
    reranked_docs = []
    for result in ranked_results[:top_k]:
        original_idx = result["id"]
        reranked_docs.append(docs[original_idx])

    logger.debug(
        "Re-ranked %d candidates → top %d (model=%s)",
        len(docs),
        len(reranked_docs),
        model_name,
    )
    return reranked_docs

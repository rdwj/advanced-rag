"""Provider implementations for RAG pipeline.

This package contains embedding and reranking provider implementations
for various backends:

- OpenAI-compatible (OpenAI, vLLM, TEI, Azure)
- Cohere embeddings and reranking
- Jina AI reranking
- Caikit NLP (IBM/Red Hat model serving)

Usage:
    from rag_core.providers import (
        EmbeddingProvider,
        RerankProvider,
        PassthroughRerankProvider,
        OpenAICompatEmbeddingProvider,
        CohereEmbeddingProvider,
        CohereRerankProvider,
        JinaRerankProvider,
        CaikitEmbeddingProvider,
        CaikitRerankProvider,
    )

    # Create an embedding provider
    embed_provider = OpenAICompatEmbeddingProvider(
        api_key="sk-...",
        model="text-embedding-3-small",
    )

    # Create a Caikit embedding provider
    caikit_embed = CaikitEmbeddingProvider(
        base_url="https://model-service.apps.cluster.com",
        model="granite-embedding-278m",
    )

    # Create a rerank provider
    rerank_provider = CohereRerankProvider(
        api_key="co-...",
        model="rerank-english-v3.0",
    )
"""
from .base import (
    EmbeddingProvider,
    EmbeddingResult,
    PassthroughRerankProvider,
    RerankProvider,
    RerankResult,
)
from .caikit_embed import CaikitEmbeddingProvider
from .caikit_rerank import CaikitRerankProvider
from .cohere_embed import CohereEmbeddingProvider
from .cohere_rerank import CohereRerankProvider
from .jina_rerank import JinaRerankProvider
from .openai_compat import OpenAICompatEmbeddingProvider

__all__ = [
    # Base classes
    "EmbeddingProvider",
    "EmbeddingResult",
    "RerankProvider",
    "RerankResult",
    "PassthroughRerankProvider",
    # Embedding providers
    "OpenAICompatEmbeddingProvider",
    "CohereEmbeddingProvider",
    "CaikitEmbeddingProvider",
    # Rerank providers
    "CohereRerankProvider",
    "JinaRerankProvider",
    "CaikitRerankProvider",
]

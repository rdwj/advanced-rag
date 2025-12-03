"""RAG Core Library - Unified embedding and reranking for RAG pipelines.

This library provides a consolidated implementation for embedding and reranking
across all RAG pipeline services and scripts. It supports:

- Multiple embedding providers (OpenAI, Cohere, vLLM, TEI)
- Multiple reranking providers (Cohere, Jina)
- YAML-based configuration with environment variable overrides
- Service-first pattern (call microservice if available, else direct API)
- Automatic batching and token limit handling

Quick Start:
    from rag_core import embed_texts, rerank_documents

    # Embed texts
    vectors = embed_texts(["Hello", "World"])

    # Rerank documents
    indices = rerank_documents("query", ["doc1", "doc2", "doc3"])

Configuration:
    Create a rag-config.yaml file or use environment variables:

    Environment Variables:
    - OPENAI_API_KEY: Default API key
    - EMBEDDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_BASE_URL
    - RERANK_PROVIDER, RERANK_API_KEY, RERANK_MODEL
    - COHERE_API_KEY: For Cohere services
    - EMBEDDING_SERVICE_URL, RERANK_SERVICE_URL: Microservice URLs

    Config File (rag-config.yaml):
    ```yaml
    embedding:
      active: openai
      providers:
        openai:
          type: openai-compatible
          api_key_env: OPENAI_API_KEY
          model: text-embedding-3-small

    rerank:
      active: cohere
      providers:
        cohere:
          type: cohere
          api_key_env: COHERE_API_KEY
          model: rerank-english-v3.0
    ```
"""
from .config import (
    RerankSettings,
    get_embedding_client,
    get_embedding_config,
    get_embedding_model,
    get_openai_client,
    get_rerank_client,
    get_rerank_config,
    get_rerank_settings,
    get_service_url,
    load_config,
)
from .embed import embed_query, embed_texts
from .models import (
    EmbeddingConfig,
    EmbeddingProviderConfig,
    ProviderConfig,
    RagConfig,
    RerankConfig,
    RerankProviderConfig,
    ServicesConfig,
)
from .rerank import (
    get_rerank_config_for_backward_compat,
    rerank_documents,
    rerank_pass_through,
    rerank_with_scores,
)
from .token_utils import (
    count_tokens_in_messages,
    estimate_tokens,
    exceeds_context,
    truncate_to_tokens,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Main functions
    "embed_texts",
    "embed_query",
    "rerank_documents",
    "rerank_with_scores",
    "rerank_pass_through",
    # Config functions
    "load_config",
    "get_embedding_config",
    "get_embedding_client",
    "get_embedding_model",
    "get_openai_client",
    "get_rerank_config",
    "get_rerank_settings",
    "get_rerank_client",
    "get_service_url",
    "get_rerank_config_for_backward_compat",
    # Models
    "RagConfig",
    "EmbeddingConfig",
    "RerankConfig",
    "ServicesConfig",
    "ProviderConfig",
    "EmbeddingProviderConfig",
    "RerankProviderConfig",
    "RerankSettings",
    # Token utilities
    "estimate_tokens",
    "exceeds_context",
    "truncate_to_tokens",
    "count_tokens_in_messages",
]

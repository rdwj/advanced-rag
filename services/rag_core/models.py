"""Pydantic models for RAG configuration.

These models define the structure for rag-config.yaml configuration files
and provide type-safe access to embedding and reranking settings.

Configuration Hierarchy:
1. Environment variable overrides (highest priority)
2. YAML config file values
3. Default values from model definitions (lowest priority)

Example rag-config.yaml:
```yaml
embedding:
  active: openai
  providers:
    openai:
      type: openai-compatible
      api_key_env: OPENAI_API_KEY
      model: text-embedding-3-small
      dimensions: 1536
    local-tei:
      type: openai-compatible
      base_url: http://localhost:8080/v1
      api_key_env: TEI_API_KEY
      model: BAAI/bge-base-en-v1.5

rerank:
  active: cohere
  providers:
    cohere:
      type: cohere
      api_key_env: COHERE_API_KEY
      model: rerank-english-v3.0
    none:
      type: passthrough

services:
  embedding_service_url: http://embedding-service:8000
  rerank_service_url: http://rerank-service:8000
```
"""
from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Base configuration for a provider.

    Attributes:
        type: Provider type identifier. Valid values:
            - "openai-compatible": OpenAI API or compatible endpoints (vLLM, TEI)
            - "cohere": Cohere API
            - "jina": Jina AI API
            - "passthrough": No-op provider (for reranking)
        base_url: API endpoint URL. If not set, uses provider's default.
        api_key_env: Name of environment variable containing the API key.
            The actual key is resolved at runtime, not stored in config.
        model: Model identifier to use with the provider.
            Optional for "passthrough" type.
    """
    type: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    model: Optional[str] = None


class EmbeddingProviderConfig(ProviderConfig):
    """Configuration for an embedding provider.

    Attributes:
        dimensions: Output embedding dimensions. Some providers support
            dimension reduction (e.g., text-embedding-3-small).
        max_batch: Maximum number of texts per embedding API call.
        max_tokens_per_input: Maximum tokens allowed per input text.
            Texts exceeding this will be truncated.
    """
    dimensions: Optional[int] = None
    max_batch: int = 64
    max_tokens_per_input: int = 8191


class RerankProviderConfig(ProviderConfig):
    """Configuration for a reranking provider.

    Attributes:
        max_documents: Maximum documents to accept for reranking.
    """
    max_documents: int = 1000


class EmbeddingConfig(BaseModel):
    """Top-level embedding configuration.

    Attributes:
        active: Name of the provider to use from the providers dict.
            Can be overridden with RAG_EMBEDDING_PROVIDER env var.
        providers: Dict of named provider configurations.
    """
    active: str = "openai"
    providers: Dict[str, EmbeddingProviderConfig] = Field(default_factory=dict)


class RerankConfig(BaseModel):
    """Top-level reranking configuration.

    Attributes:
        active: Name of the provider to use from the providers dict.
            Can be overridden with RAG_RERANK_PROVIDER env var.
            Set to "none" to disable reranking.
        providers: Dict of named provider configurations.
    """
    active: str = "none"
    providers: Dict[str, RerankProviderConfig] = Field(default_factory=dict)


class ServicesConfig(BaseModel):
    """Configuration for service-first pattern.

    When service URLs are set, the library will attempt to call
    the service first before falling back to direct provider calls.

    Attributes:
        embedding_service_url: URL of the embedding microservice.
            Overridden by EMBEDDING_SERVICE_URL env var.
        rerank_service_url: URL of the rerank microservice.
            Overridden by RERANK_SERVICE_URL env var.
    """
    embedding_service_url: Optional[str] = None
    rerank_service_url: Optional[str] = None


class RagConfig(BaseModel):
    """Root configuration model for RAG pipeline.

    This model represents the complete rag-config.yaml structure.

    Attributes:
        embedding: Embedding provider configuration.
        rerank: Reranking provider configuration.
        services: Service URL configuration for microservices deployment.
    """
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)


# Backward compatibility type alias
RerankSettings = RerankProviderConfig

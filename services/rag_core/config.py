"""Configuration loader for RAG pipeline.

This module provides a unified configuration system that:
1. Loads from rag-config.yaml if present
2. Falls back to environment variables if no config file found
3. Allows environment variable overrides even when config file exists

Configuration File Search Order:
1. RAG_CONFIG_PATH environment variable (explicit path)
2. ./rag-config.yaml (current directory)
3. ./config/rag-config.yaml (config subdirectory)
4. ./services/config/rag-config.yaml (services config)
5. ~/Developer/advanced-rag/services/config/rag-config.yaml (project default)

Environment Variable Overrides:
- RAG_EMBEDDING_PROVIDER: Override active embedding provider
- RAG_RERANK_PROVIDER: Override active rerank provider
- EMBEDDING_SERVICE_URL: Override embedding service URL
- RERANK_SERVICE_URL: Override rerank service URL

Legacy Environment Variables (for backward compatibility):
- EMBEDDING_API_KEY, OPENAI_API_KEY: API keys for embeddings
- EMBEDDING_BASE_URL, OPENAI_BASE_URL: Base URLs for embedding API
- EMBEDDING_MODEL, OPENAI_EMBEDDING_MODEL: Embedding model name
- RERANK_PROVIDER, RERANK_API_KEY, RERANK_MODEL: Rerank settings
- COHERE_API_KEY: Cohere-specific API key

Usage:
    from rag_core.config import load_config, get_embedding_config, get_embedding_client

    # Load full config
    config = load_config()

    # Get active embedding provider config
    embed_config = get_embedding_config()

    # Get configured OpenAI client for embeddings
    client = get_embedding_client()
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from openai import OpenAI

from .models import (
    EmbeddingConfig,
    EmbeddingProviderConfig,
    RagConfig,
    RerankConfig,
    RerankProviderConfig,
    ServicesConfig,
)


# Config search paths in priority order
CONFIG_SEARCH_PATHS = [
    Path("./rag-config.yaml"),
    Path("./config/rag-config.yaml"),
    Path("./services/config/rag-config.yaml"),
    Path.home() / "Developer/advanced-rag/services/config/rag-config.yaml",
]


@dataclass
class RerankSettings:
    """Backward-compatible settings for reranking.

    This dataclass mirrors the legacy config pattern for existing code
    that uses get_rerank_settings().
    """
    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]


def _find_config_file() -> Optional[Path]:
    """Find the configuration file using search order.

    Returns:
        Path to config file if found, None otherwise.
    """
    # Check explicit path first
    explicit_path = os.environ.get("RAG_CONFIG_PATH")
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return path
        # If explicit path is set but doesn't exist, don't search further
        return None

    # Search default locations
    for path in CONFIG_SEARCH_PATHS:
        if path.exists():
            return path

    return None


def _load_yaml_config(path: Path) -> dict:
    """Load and parse YAML configuration file.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed configuration dict.

    Raises:
        ValueError: If YAML parsing fails.
    """
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse config file {path}: {e}") from e


def _build_config_from_env() -> RagConfig:
    """Build configuration from environment variables only.

    This is used when no config file is found, providing backward
    compatibility with existing deployments that use environment variables.

    Returns:
        RagConfig built from environment variables.
    """
    # Build embedding config from env vars
    embed_model = os.environ.get(
        "EMBEDDING_MODEL",
        os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    embed_base_url = os.environ.get("EMBEDDING_BASE_URL") or os.environ.get("OPENAI_BASE_URL")

    embedding_providers = {
        "openai": EmbeddingProviderConfig(
            type="openai-compatible",
            base_url=embed_base_url,
            api_key_env="EMBEDDING_API_KEY",  # Resolved at runtime
            model=embed_model,
        )
    }

    # Build rerank config from env vars
    rerank_provider = os.environ.get("RERANK_PROVIDER", "none").lower()
    if rerank_provider in {"", "none"}:
        rerank_provider = "none"

    rerank_providers: dict[str, RerankProviderConfig] = {
        "none": RerankProviderConfig(
            type="passthrough",
            model="none",
        )
    }

    if rerank_provider == "cohere":
        default_model = "rerank-english-v3.0"
        rerank_model = os.environ.get(
            "RERANK_MODEL",
            os.environ.get("OPENAI_RERANK_MODEL", default_model)
        )
        rerank_base_url = os.environ.get("RERANK_BASE_URL")
        rerank_providers["cohere"] = RerankProviderConfig(
            type="cohere",
            base_url=rerank_base_url,
            api_key_env="COHERE_API_KEY",
            model=rerank_model,
        )
    elif rerank_provider not in {"", "none"}:
        # Generic provider from env
        default_model = "gpt-4.1-mini"
        rerank_model = os.environ.get(
            "RERANK_MODEL",
            os.environ.get("OPENAI_RERANK_MODEL", default_model)
        )
        rerank_base_url = os.environ.get("RERANK_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        rerank_providers[rerank_provider] = RerankProviderConfig(
            type="openai-compatible",
            base_url=rerank_base_url,
            api_key_env="RERANK_API_KEY",
            model=rerank_model,
        )

    # Build services config
    services = ServicesConfig(
        embedding_service_url=os.environ.get("EMBEDDING_SERVICE_URL"),
        rerank_service_url=os.environ.get("RERANK_SERVICE_URL"),
    )

    return RagConfig(
        embedding=EmbeddingConfig(
            active="openai",
            providers=embedding_providers,
        ),
        rerank=RerankConfig(
            active=rerank_provider,
            providers=rerank_providers,
        ),
        services=services,
    )


def _apply_env_overrides(config: RagConfig) -> RagConfig:
    """Apply environment variable overrides to config.

    Even when a config file is present, certain environment variables
    can override specific settings.

    Args:
        config: Base configuration from file.

    Returns:
        Configuration with env overrides applied.
    """
    # Override active providers
    if embed_provider := os.environ.get("RAG_EMBEDDING_PROVIDER"):
        config.embedding.active = embed_provider

    if rerank_provider := os.environ.get("RAG_RERANK_PROVIDER"):
        config.rerank.active = rerank_provider

    # Override service URLs
    if embed_url := os.environ.get("EMBEDDING_SERVICE_URL"):
        config.services.embedding_service_url = embed_url

    if rerank_url := os.environ.get("RERANK_SERVICE_URL"):
        config.services.rerank_service_url = rerank_url

    return config


@lru_cache(maxsize=1)
def load_config() -> RagConfig:
    """Load and cache RAG configuration.

    Searches for config file in standard locations, falls back to
    environment variables if not found, and applies any env overrides.

    Returns:
        Complete RagConfig with all settings resolved.

    Note:
        Configuration is cached after first load. Use load_config.cache_clear()
        to force reload.
    """
    config_path = _find_config_file()

    if config_path:
        raw_config = _load_yaml_config(config_path)
        config = RagConfig.model_validate(raw_config)
    else:
        config = _build_config_from_env()

    return _apply_env_overrides(config)


def get_embedding_config() -> EmbeddingProviderConfig:
    """Get the active embedding provider configuration.

    Returns:
        Configuration for the currently active embedding provider.

    Raises:
        KeyError: If active provider not found in providers dict.
    """
    config = load_config()
    active = config.embedding.active

    if active not in config.embedding.providers:
        # Build default provider from env if not in config
        if active == "openai":
            embed_model = os.environ.get(
                "EMBEDDING_MODEL",
                os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            )
            embed_base_url = os.environ.get("EMBEDDING_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            return EmbeddingProviderConfig(
                type="openai-compatible",
                base_url=embed_base_url,
                api_key_env="EMBEDDING_API_KEY",
                model=embed_model,
            )
        raise KeyError(f"Embedding provider '{active}' not found in config")

    return config.embedding.providers[active]


def get_rerank_config() -> Optional[RerankProviderConfig]:
    """Get the active reranking provider configuration.

    Returns:
        Configuration for the currently active rerank provider,
        or None if reranking is disabled.
    """
    config = load_config()
    active = config.rerank.active

    if active in {"", "none"}:
        return None

    if active not in config.rerank.providers:
        # Build default provider from env if not in config
        if active == "cohere":
            rerank_model = os.environ.get(
                "RERANK_MODEL",
                os.environ.get("OPENAI_RERANK_MODEL", "rerank-english-v3.0")
            )
            return RerankProviderConfig(
                type="cohere",
                base_url=os.environ.get("RERANK_BASE_URL"),
                api_key_env="COHERE_API_KEY",
                model=rerank_model,
            )
        raise KeyError(f"Rerank provider '{active}' not found in config")

    return config.rerank.providers[active]


def _resolve_api_key(provider_config: EmbeddingProviderConfig | RerankProviderConfig) -> Optional[str]:
    """Resolve API key from environment variable.

    Args:
        provider_config: Provider config with api_key_env field.

    Returns:
        API key value from environment, or None if not found.
    """
    if not provider_config.api_key_env:
        return None

    # Check the specified env var first
    api_key = os.environ.get(provider_config.api_key_env)
    if api_key:
        return api_key

    # Fallback chain for common cases
    if provider_config.api_key_env in ("EMBEDDING_API_KEY",):
        api_key = os.environ.get("OPENAI_API_KEY")

    if provider_config.api_key_env in ("RERANK_API_KEY",):
        api_key = os.environ.get("OPENAI_API_KEY")

    if provider_config.api_key_env in ("COHERE_API_KEY",):
        api_key = os.environ.get("RERANK_API_KEY")

    return api_key


def _build_openai_client(api_key: str, base_url: Optional[str]) -> OpenAI:
    """Build an OpenAI client with given credentials.

    Args:
        api_key: API key for authentication.
        base_url: Optional base URL for API endpoint.

    Returns:
        Configured OpenAI client.
    """
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def get_embedding_client() -> OpenAI:
    """Get an OpenAI client configured for embeddings.

    Returns:
        OpenAI client with embedding credentials.

    Raises:
        RuntimeError: If no API key is available.
    """
    provider_config = get_embedding_config()

    # Resolve API key
    api_key = _resolve_api_key(provider_config)
    if not api_key:
        # Final fallback to OPENAI_API_KEY
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No API key found for embeddings. Set EMBEDDING_API_KEY or OPENAI_API_KEY, "
            "or configure api_key_env in rag-config.yaml"
        )

    return _build_openai_client(api_key, provider_config.base_url)


def get_embedding_model() -> str:
    """Get the configured embedding model name.

    Returns:
        Model identifier string.
    """
    return get_embedding_config().model


def get_rerank_settings() -> Optional[RerankSettings]:
    """Get reranking settings in legacy format.

    This function provides backward compatibility with existing code
    that expects RerankSettings dataclass.

    Returns:
        RerankSettings dataclass or None if reranking disabled.
    """
    provider_config = get_rerank_config()
    if not provider_config:
        return None

    api_key = _resolve_api_key(provider_config)
    if not api_key and provider_config.type != "passthrough":
        # Final fallback for cohere
        if provider_config.type == "cohere":
            api_key = os.environ.get("COHERE_API_KEY") or os.environ.get("RERANK_API_KEY")
        else:
            api_key = os.environ.get("RERANK_API_KEY") or os.environ.get("OPENAI_API_KEY")

    return RerankSettings(
        provider=provider_config.type,
        model=provider_config.model,
        api_key=api_key,
        base_url=provider_config.base_url,
    )


def get_rerank_client() -> Optional[OpenAI]:
    """Get an OpenAI client configured for reranking.

    Only returns a client for OpenAI-compatible providers.

    Returns:
        OpenAI client if using OpenAI provider, None otherwise.
    """
    settings = get_rerank_settings()
    if not settings or settings.provider not in ("openai-compatible", "openai"):
        return None
    return _build_openai_client(settings.api_key or "", settings.base_url)


def get_service_url(service: str) -> Optional[str]:
    """Get URL for a microservice.

    Args:
        service: Service name ("embedding" or "rerank").

    Returns:
        Service URL if configured, None otherwise.
    """
    config = load_config()
    if service == "embedding":
        return config.services.embedding_service_url
    if service == "rerank":
        return config.services.rerank_service_url
    return None


# Re-export for backward compatibility
def get_openai_client() -> OpenAI:
    """Get an OpenAI client (legacy alias for get_embedding_client)."""
    return get_embedding_client()

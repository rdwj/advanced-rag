"""HTTP client for vector-gateway service."""

import os
import httpx
from typing import Any

# Default to internal OpenShift service URL
VECTOR_GATEWAY_URL = os.environ.get(
    "VECTOR_GATEWAY_URL",
    "http://vector-gateway.advanced-rag.svc.cluster.local:8000"
)


class VectorClientError(Exception):
    """Base exception for vector client errors."""
    pass


class CollectionNotFoundError(VectorClientError):
    """Raised when a collection is not found."""
    pass


class ServiceUnavailableError(VectorClientError):
    """Raised when the vector gateway is unavailable."""
    pass


class VectorClient:
    """HTTP client for interacting with the vector-gateway service."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or VECTOR_GATEWAY_URL).rstrip("/")
        self.timeout = timeout

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 5,
        context_window: int = 0,
        file_name: str | None = None,
        file_pattern: str | None = None,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for documents in a collection.

        Args:
            query: Natural language search query
            collection: Collection name to search
            top_k: Number of results to return
            context_window: Number of surrounding chunks to include
            file_name: Filter by exact file name
            file_pattern: Filter by glob pattern (e.g., "DMC-BRAKE*")
            mime_type: Filter by MIME type

        Returns:
            Search response with hits, count, latency_ms, etc.

        Raises:
            CollectionNotFoundError: If collection doesn't exist
            ServiceUnavailableError: If gateway is unreachable
            VectorClientError: For other errors
        """
        payload: dict[str, Any] = {
            "query": query,
            "collection": collection,
            "top_k": top_k,
            "context_window": context_window,
        }

        # Build filters if any are provided
        filters = {}
        if file_name:
            filters["file_name"] = file_name
        if file_pattern:
            filters["file_pattern"] = file_pattern
        if mime_type:
            filters["mime_type"] = mime_type
        if filters:
            payload["filters"] = filters

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/search", json=payload)

                if resp.status_code == 404:
                    raise CollectionNotFoundError(
                        f"Collection '{collection}' not found. Use rag_list_collections to see available collections."
                    )
                resp.raise_for_status()
                return resp.json()

        except httpx.ConnectError as exc:
            raise ServiceUnavailableError(
                "Vector search temporarily unavailable. Retry in a few seconds."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ServiceUnavailableError(
                "Vector search timed out. Try again with a smaller top_k or simpler query."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise VectorClientError(f"Search failed: {exc.response.text}") from exc

    async def list_collections(self) -> list[str]:
        """
        List all available collections.

        Returns:
            List of collection names

        Raises:
            ServiceUnavailableError: If gateway is unreachable
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/collections")
                resp.raise_for_status()
                data = resp.json()
                return data.get("collections", [])

        except httpx.ConnectError as exc:
            raise ServiceUnavailableError(
                "Vector gateway temporarily unavailable. Retry in a few seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise VectorClientError(f"Failed to list collections: {exc.response.text}") from exc

    async def get_collection_stats(self, collection: str) -> dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            collection: Collection name

        Returns:
            Stats dict with name, row_count, file_names, mime_types

        Raises:
            CollectionNotFoundError: If collection doesn't exist
            ServiceUnavailableError: If gateway is unreachable
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/collections/{collection}/stats")

                if resp.status_code == 404:
                    raise CollectionNotFoundError(
                        f"Collection '{collection}' not found. Use rag_list_collections to see available collections."
                    )
                resp.raise_for_status()
                data = resp.json()
                return data.get("stats", {})

        except httpx.ConnectError as exc:
            raise ServiceUnavailableError(
                "Vector gateway temporarily unavailable. Retry in a few seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise VectorClientError(f"Failed to get stats: {exc.response.text}") from exc

    async def health_check(self) -> bool:
        """Check if the vector gateway is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/healthz")
                return resp.status_code == 200
        except Exception:
            return False

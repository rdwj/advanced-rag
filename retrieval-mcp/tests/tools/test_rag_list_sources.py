"""Tests for rag_list_sources tool."""

import json
import pytest
from unittest.mock import patch, AsyncMock
from fastmcp.exceptions import ToolError
from tools.rag_list_sources import rag_list_sources

# Access the underlying function for testing (FastMCP decorator pattern)
rag_list_sources_fn = rag_list_sources.fn


MOCK_COLLECTION_STATS = {
    "name": "s1000d_bikes",
    "row_count": 450,
    "file_names": [
        "DMC-BRAKE-AAA.pdf",
        "DMC-WHEEL-BBB.pdf",
        "DMC-CHAIN-CCC.pdf",
    ],
    "mime_types": ["application/pdf"],
}


@pytest.mark.asyncio
async def test_rag_list_sources_concise():
    """Test listing sources in concise format."""
    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.return_value = MOCK_COLLECTION_STATS
        mock_client_class.return_value = mock_client

        result = await rag_list_sources_fn(collection="s1000d_bikes")

        assert "- DMC-BRAKE-AAA.pdf" in result
        assert "- DMC-WHEEL-BBB.pdf" in result
        assert "- DMC-CHAIN-CCC.pdf" in result

        # Verify it's a bullet list, not JSON
        assert "{" not in result


@pytest.mark.asyncio
async def test_rag_list_sources_detailed():
    """Test listing sources with detailed stats."""
    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.return_value = MOCK_COLLECTION_STATS
        mock_client_class.return_value = mock_client

        result = await rag_list_sources_fn(
            collection="s1000d_bikes",
            response_format="detailed",
        )

        data = json.loads(result)
        assert data["collection"] == "s1000d_bikes"
        assert data["total_sources"] == 3
        assert data["chunk_count"] == 450
        assert len(data["sources"]) == 3
        assert data["sources"][0]["file_name"] == "DMC-BRAKE-AAA.pdf"


@pytest.mark.asyncio
async def test_rag_list_sources_with_limit():
    """Test that limit restricts number of sources returned."""
    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.return_value = {
            "file_names": [f"doc{i}.pdf" for i in range(100)],
            "row_count": 1000,
            "mime_types": ["application/pdf"],
        }
        mock_client_class.return_value = mock_client

        result = await rag_list_sources_fn(
            collection="test",
            response_format="detailed",
            limit=10,
        )

        data = json.loads(result)
        assert data["total_sources"] == 100  # Original count
        assert data["shown"] == 10  # Respects limit
        assert len(data["sources"]) == 10


@pytest.mark.asyncio
async def test_rag_list_sources_empty_collection():
    """Test when collection has no sources."""
    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.return_value = {
            "file_names": [],
            "row_count": 0,
            "mime_types": [],
        }
        mock_client_class.return_value = mock_client

        result = await rag_list_sources_fn(collection="empty_collection")

        assert "No sources found" in result


@pytest.mark.asyncio
async def test_rag_list_sources_empty_collection_name():
    """Test that empty collection name raises error."""
    with pytest.raises(ToolError, match="Collection name is required"):
        await rag_list_sources_fn(collection="")

    with pytest.raises(ToolError, match="Collection name is required"):
        await rag_list_sources_fn(collection="   ")


@pytest.mark.asyncio
async def test_rag_list_sources_invalid_format():
    """Test that invalid response_format raises error."""
    with pytest.raises(ToolError, match="response_format must be"):
        await rag_list_sources_fn(collection="test", response_format="invalid")


@pytest.mark.asyncio
async def test_rag_list_sources_invalid_limit():
    """Test that invalid limit raises error."""
    with pytest.raises(ToolError, match="limit must be between"):
        await rag_list_sources_fn(collection="test", limit=0)

    with pytest.raises(ToolError, match="limit must be between"):
        await rag_list_sources_fn(collection="test", limit=1000)


@pytest.mark.asyncio
async def test_rag_list_sources_collection_not_found():
    """Test handling collection not found with helpful message."""
    from lib.vector_client import CollectionNotFoundError

    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.side_effect = CollectionNotFoundError("Not found")
        mock_client.list_collections.return_value = ["collection_a", "collection_b"]
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError) as exc_info:
            await rag_list_sources_fn(collection="bad_collection")

        assert "bad_collection" in str(exc_info.value)
        assert "collection_a" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rag_list_sources_service_unavailable():
    """Test handling service unavailability."""
    from lib.vector_client import ServiceUnavailableError

    with patch("tools.rag_list_sources.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_collection_stats.side_effect = ServiceUnavailableError(
            "Vector gateway temporarily unavailable"
        )
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError, match="temporarily unavailable"):
            await rag_list_sources_fn(collection="test")

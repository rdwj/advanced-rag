"""Tests for rag_list_collections tool."""

import json
import pytest
from unittest.mock import patch, AsyncMock
from fastmcp.exceptions import ToolError
from tools.rag_list_collections import rag_list_collections

# Access the underlying function for testing (FastMCP decorator pattern)
rag_list_collections_fn = rag_list_collections.fn


@pytest.mark.asyncio
async def test_rag_list_collections_concise():
    """Test listing collections in concise format."""
    with patch("tools.rag_list_collections.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.list_collections.return_value = [
            "s1000d_bikes",
            "product_manuals",
            "support_tickets",
        ]
        mock_client_class.return_value = mock_client

        result = await rag_list_collections_fn()

        # Should be valid JSON array
        collections = json.loads(result)
        assert collections == ["s1000d_bikes", "product_manuals", "support_tickets"]


@pytest.mark.asyncio
async def test_rag_list_collections_detailed():
    """Test listing collections with detailed stats."""
    with patch("tools.rag_list_collections.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.list_collections.return_value = ["s1000d_bikes", "product_manuals"]
        mock_client.get_collection_stats.side_effect = [
            {
                "name": "s1000d_bikes",
                "row_count": 450,
                "file_names": ["doc1.pdf", "doc2.pdf", "doc3.pdf"],
                "mime_types": ["application/pdf", "text/html"],
            },
            {
                "name": "product_manuals",
                "row_count": 200,
                "file_names": ["manual1.pdf"],
                "mime_types": ["application/pdf"],
            },
        ]
        mock_client_class.return_value = mock_client

        result = await rag_list_collections_fn(response_format="detailed")

        # Should be valid JSON with detailed info
        data = json.loads(result)
        assert len(data) == 2

        assert data[0]["name"] == "s1000d_bikes"
        assert data[0]["document_count"] == 3
        assert data[0]["chunk_count"] == 450
        assert "application/pdf" in data[0]["file_types"]

        assert data[1]["name"] == "product_manuals"
        assert data[1]["document_count"] == 1


@pytest.mark.asyncio
async def test_rag_list_collections_empty():
    """Test when no collections exist."""
    with patch("tools.rag_list_collections.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.list_collections.return_value = []
        mock_client_class.return_value = mock_client

        result = await rag_list_collections_fn()

        assert "No collections found" in result


@pytest.mark.asyncio
async def test_rag_list_collections_invalid_format():
    """Test that invalid response_format raises error."""
    with pytest.raises(ToolError, match="response_format must be"):
        await rag_list_collections_fn(response_format="invalid")


@pytest.mark.asyncio
async def test_rag_list_collections_service_unavailable():
    """Test handling service unavailability."""
    from lib.vector_client import ServiceUnavailableError

    with patch("tools.rag_list_collections.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.list_collections.side_effect = ServiceUnavailableError(
            "Vector gateway temporarily unavailable"
        )
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError, match="temporarily unavailable"):
            await rag_list_collections_fn()


@pytest.mark.asyncio
async def test_rag_list_collections_detailed_stats_error():
    """Test that detailed format handles stats errors gracefully."""
    with patch("tools.rag_list_collections.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.list_collections.return_value = ["collection_a", "collection_b"]
        # First call succeeds, second fails
        mock_client.get_collection_stats.side_effect = [
            {
                "name": "collection_a",
                "row_count": 100,
                "file_names": ["doc.pdf"],
                "mime_types": ["application/pdf"],
            },
            Exception("Stats unavailable"),
        ]
        mock_client_class.return_value = mock_client

        result = await rag_list_collections_fn(response_format="detailed")

        data = json.loads(result)
        assert len(data) == 2

        # First collection has full stats
        assert data[0]["chunk_count"] == 100

        # Second collection has minimal info (just name)
        assert data[1]["name"] == "collection_b"
        assert "chunk_count" not in data[1]

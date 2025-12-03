"""Tests for rag_search tool."""

import pytest
from unittest.mock import patch, AsyncMock
from fastmcp.exceptions import ToolError
from tools.rag_search import rag_search

# Access the underlying function for testing (FastMCP decorator pattern)
rag_search_fn = rag_search.fn


# Mock search response from vector gateway
MOCK_SEARCH_RESPONSE = {
    "hits": [
        {
            "doc_id": "test-1",
            "text": "The brake pads should be replaced every 5000 miles.",
            "score": 0.95,
            "metadata": {
                "entity": {
                    "file_name": "DMC-BRAKE-AAA.pdf",
                    "page": 3,
                    "chunk_index": 0,
                }
            },
            "surrounding_chunks": [],
        },
        {
            "doc_id": "test-2",
            "text": "To adjust brake tension, turn the barrel adjuster.",
            "score": 0.87,
            "metadata": {
                "entity": {
                    "file_name": "DMC-BRAKE-AAA.pdf",
                    "page": 4,
                    "chunk_index": 1,
                }
            },
            "surrounding_chunks": [
                {"chunk_index": 0, "text": "Preceding chunk", "page": 3}
            ],
        },
    ],
    "count": 2,
    "latency_ms": 150,
    "backend": "milvus",
    "collection": "test_collection",
    "reranked": True,
}


@pytest.mark.asyncio
async def test_rag_search_basic():
    """Test basic rag_search functionality with concise format."""
    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = MOCK_SEARCH_RESPONSE
        mock_client_class.return_value = mock_client

        result = await rag_search_fn(
            query="how to adjust brakes",
            collection="test_collection",
        )

        # Check that result contains expected citation format
        assert "[1]" in result
        assert "brake pads" in result
        assert "DMC-BRAKE-AAA.pdf" in result
        assert "Page 3" in result

        # Verify client was called correctly
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["query"] == "how to adjust brakes"
        assert call_kwargs["collection"] == "test_collection"
        assert call_kwargs["top_k"] == 5  # default
        assert call_kwargs["context_window"] == 2  # default


@pytest.mark.asyncio
async def test_rag_search_detailed_format():
    """Test rag_search with detailed JSON format."""
    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = MOCK_SEARCH_RESPONSE
        mock_client_class.return_value = mock_client

        result = await rag_search_fn(
            query="brake adjustment",
            collection="test_collection",
            response_format="detailed",
        )

        # Should be valid JSON with results array
        import json
        data = json.loads(result)
        assert "results" in data
        assert "total_found" in data
        assert "query_time_ms" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 0.95


@pytest.mark.asyncio
async def test_rag_search_with_filters():
    """Test rag_search with metadata filters."""
    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = MOCK_SEARCH_RESPONSE
        mock_client_class.return_value = mock_client

        await rag_search_fn(
            query="brakes",
            collection="test_collection",
            file_pattern="DMC-BRAKE*",
            mime_type="application/pdf",
        )

        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["file_pattern"] == "DMC-BRAKE*"
        assert call_kwargs["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_rag_search_min_score_filter():
    """Test that min_score filters out low-scoring results."""
    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = MOCK_SEARCH_RESPONSE
        mock_client_class.return_value = mock_client

        result = await rag_search_fn(
            query="brakes",
            collection="test_collection",
            min_score=0.9,  # Should filter out second hit (0.87)
            response_format="detailed",
        )

        import json
        data = json.loads(result)
        assert data["total_found"] == 1
        assert data["results"][0]["score"] == 0.95


@pytest.mark.asyncio
async def test_rag_search_no_results():
    """Test rag_search when no results are found."""
    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.return_value = {"hits": [], "count": 0, "latency_ms": 50}
        mock_client_class.return_value = mock_client

        result = await rag_search_fn(
            query="nonexistent topic",
            collection="test_collection",
        )

        assert "No matching documents" in result
        assert "rag_rewrite_query" in result  # Suggests trying query rewrite


@pytest.mark.asyncio
async def test_rag_search_empty_query():
    """Test rag_search rejects empty query."""
    with pytest.raises(ToolError, match="Query cannot be empty"):
        await rag_search_fn(query="", collection="test_collection")

    with pytest.raises(ToolError, match="Query cannot be empty"):
        await rag_search_fn(query="   ", collection="test_collection")


@pytest.mark.asyncio
async def test_rag_search_empty_collection():
    """Test rag_search rejects empty collection."""
    with pytest.raises(ToolError, match="Collection name is required"):
        await rag_search_fn(query="test query", collection="")


@pytest.mark.asyncio
async def test_rag_search_invalid_top_k():
    """Test rag_search validates top_k range."""
    with pytest.raises(ToolError, match="top_k must be between 1 and 20"):
        await rag_search_fn(query="test", collection="test", top_k=0)

    with pytest.raises(ToolError, match="top_k must be between 1 and 20"):
        await rag_search_fn(query="test", collection="test", top_k=25)


@pytest.mark.asyncio
async def test_rag_search_invalid_context_window():
    """Test rag_search validates context_window range."""
    with pytest.raises(ToolError, match="context_window must be between 0 and 5"):
        await rag_search_fn(query="test", collection="test", context_window=-1)

    with pytest.raises(ToolError, match="context_window must be between 0 and 5"):
        await rag_search_fn(query="test", collection="test", context_window=10)


@pytest.mark.asyncio
async def test_rag_search_invalid_min_score():
    """Test rag_search validates min_score range."""
    with pytest.raises(ToolError, match="min_score must be between 0.0 and 1.0"):
        await rag_search_fn(query="test", collection="test", min_score=-0.1)

    with pytest.raises(ToolError, match="min_score must be between 0.0 and 1.0"):
        await rag_search_fn(query="test", collection="test", min_score=1.5)


@pytest.mark.asyncio
async def test_rag_search_invalid_response_format():
    """Test rag_search validates response_format."""
    with pytest.raises(ToolError, match="response_format must be"):
        await rag_search_fn(query="test", collection="test", response_format="invalid")


@pytest.mark.asyncio
async def test_rag_search_service_unavailable():
    """Test rag_search handles service unavailability."""
    from lib.vector_client import ServiceUnavailableError

    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.side_effect = ServiceUnavailableError("Service down")
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError, match="Service down"):
            await rag_search_fn(query="test", collection="test_collection")


@pytest.mark.asyncio
async def test_rag_search_collection_not_found():
    """Test rag_search handles collection not found with helpful message."""
    from lib.vector_client import CollectionNotFoundError

    with patch("tools.rag_search.VectorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.search.side_effect = CollectionNotFoundError("Not found")
        mock_client.list_collections.return_value = ["collection_a", "collection_b"]
        mock_client_class.return_value = mock_client

        with pytest.raises(ToolError) as exc_info:
            await rag_search_fn(query="test", collection="bad_collection")

        # Should include available collections in error message
        assert "bad_collection" in str(exc_info.value)
        assert "collection_a" in str(exc_info.value)

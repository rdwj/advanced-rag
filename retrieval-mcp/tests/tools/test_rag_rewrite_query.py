"""Tests for rag_rewrite_query tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastmcp.exceptions import ToolError
from tools.rag_rewrite_query import rag_rewrite_query

# Access the underlying function for testing (FastMCP decorator pattern)
rag_rewrite_query_fn = rag_rewrite_query.fn


class MockSamplingResponse:
    """Mock response from ctx.sample()."""

    def __init__(self, text: str):
        self.text = text


@pytest.fixture
def mock_context():
    """Create a mock FastMCP context with sampling support."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_rag_rewrite_query_basic(mock_context):
    """Test basic query rewrite with expand style."""
    mock_context.sample.return_value = MockSamplingResponse(
        "bicycle brake system troubleshooting maintenance"
    )

    result = await rag_rewrite_query_fn(
        query="bike stopping issues",
        ctx=mock_context,
    )

    assert result == "bicycle brake system troubleshooting maintenance"
    mock_context.sample.assert_called_once()

    # Check the prompt contains the query
    call_kwargs = mock_context.sample.call_args.kwargs
    assert "bike stopping issues" in call_kwargs["messages"]
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["max_tokens"] == 100


@pytest.mark.asyncio
async def test_rag_rewrite_query_with_domain_context(mock_context):
    """Test query rewrite with domain context."""
    mock_context.sample.return_value = MockSamplingResponse(
        "brake pad replacement inspection wear indicator"
    )

    result = await rag_rewrite_query_fn(
        query="brake problems",
        domain_context="bicycle maintenance manuals",
        ctx=mock_context,
    )

    assert "brake pad" in result

    # Check domain context is in system prompt
    call_kwargs = mock_context.sample.call_args.kwargs
    assert "bicycle maintenance manuals" in call_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_rag_rewrite_query_technical_style(mock_context):
    """Test query rewrite with technical style."""
    mock_context.sample.return_value = MockSamplingResponse(
        "hydraulic disc brake caliper alignment procedure"
    )

    await rag_rewrite_query_fn(
        query="fix brake rubbing",
        rewrite_style="technical",
        ctx=mock_context,
    )

    # Check style instruction is in prompt
    call_kwargs = mock_context.sample.call_args.kwargs
    assert "technical terminology" in call_kwargs["messages"]


@pytest.mark.asyncio
async def test_rag_rewrite_query_simplify_style(mock_context):
    """Test query rewrite with simplify style."""
    mock_context.sample.return_value = MockSamplingResponse("brake adjustment")

    await rag_rewrite_query_fn(
        query="how do I make my brakes work better",
        rewrite_style="simplify",
        ctx=mock_context,
    )

    # Check style instruction is in prompt
    call_kwargs = mock_context.sample.call_args.kwargs
    assert "simplify" in call_kwargs["messages"].lower()


@pytest.mark.asyncio
async def test_rag_rewrite_query_empty_response_fallback(mock_context):
    """Test that empty LLM response returns original query."""
    mock_context.sample.return_value = MockSamplingResponse("")

    result = await rag_rewrite_query_fn(
        query="original query",
        ctx=mock_context,
    )

    assert result == "original query"
    mock_context.warning.assert_called_once()


@pytest.mark.asyncio
async def test_rag_rewrite_query_empty_query():
    """Test that empty query raises error."""
    mock_ctx = AsyncMock()

    with pytest.raises(ToolError, match="Query cannot be empty"):
        await rag_rewrite_query_fn(query="", ctx=mock_ctx)

    with pytest.raises(ToolError, match="Query cannot be empty"):
        await rag_rewrite_query_fn(query="   ", ctx=mock_ctx)


@pytest.mark.asyncio
async def test_rag_rewrite_query_invalid_style():
    """Test that invalid rewrite style raises error."""
    mock_ctx = AsyncMock()

    with pytest.raises(ToolError, match="rewrite_style must be one of"):
        await rag_rewrite_query_fn(
            query="test query",
            rewrite_style="invalid",
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_rag_rewrite_query_no_context():
    """Test that missing context raises helpful error."""
    with pytest.raises(ToolError, match="Context not available"):
        await rag_rewrite_query_fn(query="test query", ctx=None)


@pytest.mark.asyncio
async def test_rag_rewrite_query_sampling_not_supported(mock_context):
    """Test handling when client doesn't support sampling."""
    mock_context.sample.side_effect = NotImplementedError("Sampling not supported")

    with pytest.raises(ToolError, match="Client does not support sampling"):
        await rag_rewrite_query_fn(query="test query", ctx=mock_context)


@pytest.mark.asyncio
async def test_rag_rewrite_query_sampling_error(mock_context):
    """Test handling of general sampling errors."""
    mock_context.sample.side_effect = Exception("Network error")

    with pytest.raises(ToolError, match="Query rewrite failed"):
        await rag_rewrite_query_fn(query="test query", ctx=mock_context)

    # Should have logged a warning
    mock_context.warning.assert_called_once()


@pytest.mark.asyncio
async def test_rag_rewrite_query_strips_whitespace(mock_context):
    """Test that input and output are properly stripped."""
    mock_context.sample.return_value = MockSamplingResponse(
        "  cleaned query result  "
    )

    result = await rag_rewrite_query_fn(
        query="  padded query  ",
        ctx=mock_context,
    )

    assert result == "cleaned query result"

    # Check the query in prompt is stripped
    call_kwargs = mock_context.sample.call_args.kwargs
    assert "padded query" in call_kwargs["messages"]
    assert "  padded query  " not in call_kwargs["messages"]

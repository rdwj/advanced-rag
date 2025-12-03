"""Search for relevant content in a document collection using hybrid search (dense + BM25) with reranking."""

from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError

from core.app import mcp
from lib.vector_client import (
    VectorClient,
    CollectionNotFoundError,
    ServiceUnavailableError,
    VectorClientError,
)
from lib.formatters import format_concise, format_detailed


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def rag_search(
    query: Annotated[str, Field(description="Natural language search query")],
    collection: Annotated[str, Field(description="Collection to search (agent should know this from system prompt)")],
    top_k: Annotated[int, Field(description="Number of results (1-20)")] = 5,
    context_window: Annotated[int, Field(description="Number of surrounding chunks to include (0-5)")] = 2,
    file_name: Annotated[str | None, Field(description="Filter by exact file name")] = None,
    file_pattern: Annotated[str | None, Field(description="Filter by glob pattern (e.g., 'DMC-BRAKE*')")] = None,
    mime_type: Annotated[str | None, Field(description="Filter by MIME type (e.g., 'application/pdf')")] = None,
    min_score: Annotated[float, Field(description="Minimum relevance threshold (0.0-1.0)")] = 0.0,
    response_format: Annotated[str, Field(description="Output format: 'concise' (text + citations) or 'detailed' (full metadata JSON)")] = "concise",
) -> str:
    """Search for relevant content in a document collection using hybrid search (dense + BM25) with reranking.

    This is the primary retrieval tool. It embeds the query, performs hybrid search
    (dense vectors + BM25), reranks results, expands context, and returns formatted chunks.

    Args:
        query: Natural language search query
        collection: Collection to search (agent should know this from system prompt)
        top_k: Number of results (1-20)
        context_window: Number of surrounding chunks to include (0-5)
        file_name: Filter by exact file name
        file_pattern: Filter by glob pattern (e.g., 'DMC-BRAKE*')
        mime_type: Filter by MIME type (e.g., 'application/pdf')
        min_score: Minimum relevance threshold (0.0-1.0)
        response_format: Output format: 'concise' (text + citations) or 'detailed' (full metadata JSON)

    Returns:
        Formatted search results (concise citations or detailed JSON)

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate inputs
    if not query or not query.strip():
        raise ToolError("Query cannot be empty")

    if not collection or not collection.strip():
        raise ToolError("Collection name is required. Check your system prompt for the collection to use.")

    if top_k < 1 or top_k > 20:
        raise ToolError("top_k must be between 1 and 20")

    if context_window < 0 or context_window > 5:
        raise ToolError("context_window must be between 0 and 5")

    if min_score < 0.0 or min_score > 1.0:
        raise ToolError("min_score must be between 0.0 and 1.0")

    if response_format not in ("concise", "detailed"):
        raise ToolError("response_format must be 'concise' or 'detailed'")

    # Call vector gateway
    client = VectorClient()
    try:
        result = await client.search(
            query=query.strip(),
            collection=collection.strip(),
            top_k=top_k,
            context_window=context_window,
            file_name=file_name,
            file_pattern=file_pattern,
            mime_type=mime_type,
        )
    except CollectionNotFoundError as exc:
        # Get available collections to help the agent
        try:
            available = await client.list_collections()
            available_str = ", ".join(available) if available else "none"
        except Exception:
            # If we can't list collections, just use the original error
            raise ToolError(str(exc)) from exc
        raise ToolError(
            f"Collection '{collection}' not found. Available collections: {available_str}. "
            "Use rag_list_collections to see all."
        ) from exc
    except ServiceUnavailableError as exc:
        raise ToolError(str(exc)) from exc
    except VectorClientError as exc:
        raise ToolError(f"Search failed: {exc}") from exc

    # Extract hits and apply min_score filter
    hits = result.get("hits", [])
    if min_score > 0.0:
        hits = [h for h in hits if h.get("score", 0.0) >= min_score]

    # Handle no results
    if not hits:
        return (
            f"No matching documents found in '{collection}'. "
            "Try rag_rewrite_query to reformulate your query, "
            "or use rag_list_sources to see available content."
        )

    # Format response
    latency_ms = result.get("latency_ms", 0)
    if response_format == "detailed":
        return format_detailed(hits, latency_ms)
    else:
        return format_concise(hits)

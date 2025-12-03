"""List documents within a specific collection."""

import json
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


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def rag_list_sources(
    collection: Annotated[str, Field(description="Collection name to list sources from")],
    response_format: Annotated[str, Field(description="Output format: 'concise' (file names only) or 'detailed' (with chunk counts)")] = "concise",
    limit: Annotated[int, Field(description="Maximum number of sources to return")] = 50,
) -> str:
    """List documents within a specific collection.

    Use this tool to understand what documents are available in a collection,
    help users understand the scope of available content, or when the agent
    needs to filter searches by specific files.

    Args:
        collection: Collection name to list sources from
        response_format: Output format: 'concise' (file names only) or 'detailed' (with chunk counts)
        limit: Maximum number of sources to return

    Returns:
        List of source file names (concise) or detailed source info (detailed)

    Raises:
        ToolError: If validation fails or operation cannot be completed
    """
    # Validate inputs
    if not collection or not collection.strip():
        raise ToolError("Collection name is required")

    if response_format not in ("concise", "detailed"):
        raise ToolError("response_format must be 'concise' or 'detailed'")

    if limit < 1 or limit > 500:
        raise ToolError("limit must be between 1 and 500")

    client = VectorClient()
    try:
        stats = await client.get_collection_stats(collection.strip())
    except CollectionNotFoundError as exc:
        # Get available collections to help the agent
        try:
            available = await client.list_collections()
            available_str = ", ".join(available) if available else "none"
        except Exception:
            raise ToolError(str(exc)) from exc
        raise ToolError(
            f"Collection '{collection}' not found. Available collections: {available_str}. "
            "Use rag_list_collections to see all."
        ) from exc
    except ServiceUnavailableError as exc:
        raise ToolError(str(exc)) from exc
    except VectorClientError as exc:
        raise ToolError(f"Failed to get sources: {exc}") from exc

    file_names = stats.get("file_names", [])

    if not file_names:
        return f"No sources found in collection '{collection}'. Use the ingest pipeline to add documents."

    # Apply limit
    file_names = file_names[:limit]

    if response_format == "concise":
        # Simple bullet list of file names
        return "\n".join(f"- {name}" for name in file_names)
    else:
        # Detailed format with stats
        mime_types = stats.get("mime_types", [])
        row_count = stats.get("row_count", 0)

        output = {
            "collection": collection,
            "sources": [{"file_name": name} for name in file_names],
            "total_sources": len(stats.get("file_names", [])),  # Total before limit
            "shown": len(file_names),
            "chunk_count": row_count,
            "file_types": mime_types,
        }

        return json.dumps(output, indent=2)

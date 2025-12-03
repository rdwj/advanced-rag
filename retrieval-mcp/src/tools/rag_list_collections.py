"""Discover available document collections in the vector store."""

import json
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError

from core.app import mcp
from lib.vector_client import (
    VectorClient,
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
async def rag_list_collections(
    response_format: Annotated[str, Field(description="Output format: 'concise' (names only) or 'detailed' (with stats)")] = "concise",
) -> str:
    """Discover available document collections in the vector store.

    Use this tool to find out what collections are available for searching.
    Typically not needed if the agent's system prompt specifies which collection to use.

    Args:
        response_format: Output format: 'concise' (names only) or 'detailed' (with stats)

    Returns:
        List of collection names (concise) or collection info with stats (detailed)

    Raises:
        ToolError: If the operation cannot be completed
    """
    if response_format not in ("concise", "detailed"):
        raise ToolError("response_format must be 'concise' or 'detailed'")

    client = VectorClient()
    try:
        collections = await client.list_collections()
    except ServiceUnavailableError as exc:
        raise ToolError(str(exc)) from exc
    except VectorClientError as exc:
        raise ToolError(f"Failed to list collections: {exc}") from exc

    if not collections:
        return "No collections found. Use the ingest pipeline to add documents first."

    if response_format == "concise":
        return json.dumps(collections)
    else:
        # For detailed format, get stats for each collection
        detailed_info = []
        for coll_name in collections:
            try:
                stats = await client.get_collection_stats(coll_name)
                detailed_info.append({
                    "name": coll_name,
                    "document_count": len(stats.get("file_names", [])),
                    "chunk_count": stats.get("row_count", 0),
                    "file_types": stats.get("mime_types", []),
                })
            except Exception:
                # If we can't get stats, include minimal info
                detailed_info.append({"name": coll_name})

        return json.dumps(detailed_info, indent=2)

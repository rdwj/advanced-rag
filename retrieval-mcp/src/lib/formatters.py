"""Citation formatters for search results."""

import json
from typing import Any


def format_concise(hits: list[dict[str, Any]]) -> str:
    """
    Format search results as concise citations for agent consumption.

    Args:
        hits: List of search hit dicts from vector-gateway

    Returns:
        Formatted string with numbered citations

    Example output:
        [1] "The brake pads should be replaced every 5000 miles..."
            Source: DMC-BRAKE-AAA.pdf, Page 3

        [2] "To adjust brake tension, turn the barrel adjuster..."
            Source: DMC-BRAKE-AAA.pdf, Page 4
    """
    if not hits:
        return "No results found."

    lines = []
    for i, hit in enumerate(hits, 1):
        text = hit.get("text", "")
        metadata = hit.get("metadata", {})

        # Extract file_name and page from nested entity or direct metadata
        entity = metadata.get("entity", metadata)
        file_name = entity.get("file_name", "") or metadata.get("file_name", "Unknown")
        page = entity.get("page", -1)
        if page == -1:
            page = metadata.get("page", -1)

        # Format the citation
        lines.append(f'[{i}] "{text}"')
        if page >= 0:
            lines.append(f"    Source: {file_name}, Page {page}")
        else:
            lines.append(f"    Source: {file_name}")

        # Include surrounding context if available
        surrounding = hit.get("surrounding_chunks", [])
        if surrounding:
            context_texts = [c.get("text", "") for c in surrounding if c.get("text")]
            if context_texts:
                lines.append(f"    Context: {len(context_texts)} adjacent chunks available")

        lines.append("")  # Blank line between results

    return "\n".join(lines).strip()


def format_detailed(hits: list[dict[str, Any]], latency_ms: int = 0) -> str:
    """
    Format search results as detailed JSON for programmatic use.

    Args:
        hits: List of search hit dicts from vector-gateway
        latency_ms: Query latency in milliseconds

    Returns:
        JSON string with full metadata
    """
    results = []
    for hit in hits:
        metadata = hit.get("metadata", {})
        entity = metadata.get("entity", metadata)

        result = {
            "text": hit.get("text", ""),
            "score": hit.get("score", 0.0),
            "file_name": entity.get("file_name", "") or metadata.get("file_name", ""),
            "page": entity.get("page", -1),
            "chunk_index": entity.get("chunk_index", -1),
        }

        # Include surrounding context if present
        surrounding = hit.get("surrounding_chunks", [])
        if surrounding:
            result["surrounding_context"] = [c.get("text", "") for c in surrounding]

        results.append(result)

    output = {
        "results": results,
        "total_found": len(results),
        "query_time_ms": latency_ms,
    }

    return json.dumps(output, indent=2)


def format_collections_concise(collections: list[str]) -> str:
    """Format collection list as simple JSON array."""
    return json.dumps(collections)


def format_collections_detailed(
    collections: list[str],
    stats_getter: Any = None,
) -> str:
    """
    Format collections with stats. Note: This is a sync formatter.
    Use format_collections_detailed_async for async stats fetching.
    """
    # For sync use, just return the names
    return json.dumps([{"name": c} for c in collections], indent=2)


def format_sources_concise(file_names: list[str]) -> str:
    """Format source file list."""
    if not file_names:
        return "No sources found in this collection."
    return "\n".join(f"- {name}" for name in file_names)


def format_sources_detailed(stats: dict[str, Any]) -> str:
    """Format detailed source information from collection stats."""
    file_names = stats.get("file_names", [])
    mime_types = stats.get("mime_types", [])
    row_count = stats.get("row_count", 0)

    output = {
        "sources": [{"file_name": name} for name in file_names],
        "total_sources": len(file_names),
        "chunk_count": row_count,
        "file_types": mime_types,
    }

    return json.dumps(output, indent=2)

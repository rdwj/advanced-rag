"""Rewrite a query for better retrieval using LLM sampling."""

from typing import Annotated
from pydantic import Field
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core.app import mcp


STYLE_INSTRUCTIONS = {
    "expand": "Add synonyms and related terms to broaden the search.",
    "simplify": "Clarify and simplify the query for direct matching.",
    "technical": "Use precise technical terminology from the domain.",
}

SYSTEM_PROMPT = """You are a search query optimizer. Rewrite the user's query to improve retrieval from a document database.

Rules:
- Keep the core intent
- Add relevant synonyms or technical terms
- Remove filler words
- Output ONLY the rewritten query, nothing else"""


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": False,  # LLM sampling may produce different results
        "openWorldHint": False,
    }
)
async def rag_rewrite_query(
    query: Annotated[str, Field(description="Original user query to rewrite")],
    domain_context: Annotated[str | None, Field(description="Domain hints (e.g., 'technical maintenance manuals', 'medical guidelines')")] = None,
    rewrite_style: Annotated[str, Field(description="Rewrite style: 'expand' (add synonyms), 'simplify' (clarify), or 'technical' (use domain jargon)")] = "expand",
    ctx: Context = None,
) -> str:
    """Rewrite a query for better retrieval using LLM sampling.

    Use this tool when the original query is vague, uses colloquial terms,
    or could benefit from domain-specific terminology. The agent decides
    when to use this based on query quality.

    Args:
        query: Original user query to rewrite
        domain_context: Domain hints (e.g., 'technical maintenance manuals', 'medical guidelines')
        rewrite_style: Rewrite style: 'expand' (add synonyms), 'simplify' (clarify), or 'technical' (use domain jargon)
        ctx: FastMCP context for sampling

    Returns:
        The rewritten query string

    Raises:
        ToolError: If validation fails or sampling is not supported

    Example usage pattern:
        User asked: "bike stopping issues"
        -> rag_rewrite_query(query="bike stopping issues", domain_context="bicycle maintenance manuals", rewrite_style="technical")
        -> "brake system malfunction troubleshooting brake pad inspection"
        -> rag_search(query="brake system malfunction...", collection="s1000d_bikes")
    """
    # Validate inputs
    if not query or not query.strip():
        raise ToolError("Query cannot be empty")

    if rewrite_style not in STYLE_INSTRUCTIONS:
        raise ToolError(
            f"rewrite_style must be one of: {', '.join(STYLE_INSTRUCTIONS.keys())}"
        )

    # Check if context is available (required for sampling)
    if ctx is None:
        raise ToolError(
            "Query rewriting requires LLM sampling. Context not available - use rag_search directly."
        )

    # Build system prompt with domain context if provided
    system_prompt = SYSTEM_PROMPT
    if domain_context:
        system_prompt += f"\n\nDomain context: {domain_context}"

    # Build the prompt
    style_instruction = STYLE_INSTRUCTIONS[rewrite_style]
    prompt = f"""{style_instruction}

Original query: {query.strip()}

Rewritten query:"""

    # Request LLM to rewrite the query
    try:
        await ctx.info(f"Rewriting query with style '{rewrite_style}'")
        response = await ctx.sample(
            messages=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Low temperature for more focused rewrites
            max_tokens=100,
        )
        rewritten = response.text.strip()

        # Validate we got something back
        if not rewritten:
            await ctx.warning("LLM returned empty response, returning original query")
            return query.strip()

        await ctx.info(f"Query rewritten: '{query.strip()}' -> '{rewritten}'")
        return rewritten

    except NotImplementedError as exc:
        # Client doesn't support sampling
        raise ToolError(
            "Query rewriting requires LLM sampling. Client does not support sampling - use rag_search directly."
        ) from exc
    except Exception as exc:
        # Log the error and suggest using the original query
        if ctx:
            await ctx.warning(f"Query rewrite failed: {exc}")
        raise ToolError(
            f"Query rewrite failed: {exc}. Try using rag_search with the original query."
        ) from exc

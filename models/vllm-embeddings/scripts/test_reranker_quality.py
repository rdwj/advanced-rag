#!/usr/bin/env python3
"""
Test reranker quality using vLLM's /v1/score endpoint.

Usage:
    python test_reranker_quality.py --url <vllm-url> --model <model-name>

Examples:
    # Test MS-MARCO
    python test_reranker_quality.py \
        --url https://msmarco-reranker-vllm-embeddings.apps.cluster.local \
        --model cross-encoder/ms-marco-MiniLM-L12-v2

    # Test BGE
    python test_reranker_quality.py \
        --url https://bge-reranker-vllm-embeddings.apps.cluster.local \
        --model BAAI/bge-reranker-v2-m3
"""

import argparse
import json
import sys
import time
from typing import Optional

import requests

# Suppress SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_score(url: str, model: str, query: str, document: str) -> Optional[float]:
    """Get relevance score from vLLM /v1/score endpoint."""
    try:
        response = requests.post(
            f"{url}/v1/score",
            json={
                "model": model,
                "text_1": query,
                "text_2": document
            },
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        # The score format may vary - try common patterns
        if "score" in result:
            return result["score"]
        elif "data" in result and len(result["data"]) > 0:
            return result["data"][0].get("score")
        else:
            print(f"Unexpected response format: {result}")
            return None
    except Exception as e:
        print(f"Error getting score: {e}")
        return None


def rerank_documents(url: str, model: str, query: str, documents: list[str]) -> list[tuple[int, float, str]]:
    """Rerank documents by relevance to query."""
    scored = []
    for i, doc in enumerate(documents):
        score = get_score(url, model, query, doc)
        if score is not None:
            scored.append((i, score, doc))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def run_tests(url: str, model: str):
    """Run reranker quality tests."""

    print("=" * 60)
    print(f"vLLM Reranker Quality Test")
    print(f"URL: {url}")
    print(f"Model: {model}")
    print("=" * 60)

    # Test 1: Health check
    print("\n[Test 1] Health Check")
    print("-" * 40)

    try:
        response = requests.get(f"{url}/health", verify=False, timeout=10)
        if response.ok:
            print("  ✓ Server is healthy")
        else:
            print(f"  ✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Health check failed: {e}")
        return False

    # Test 2: Basic scoring
    print("\n[Test 2] Basic Score Generation")
    print("-" * 40)

    test_pairs = [
        ("What is machine learning?", "Machine learning is a branch of artificial intelligence."),
        ("What is machine learning?", "The weather is sunny today."),
        ("Capital of France", "Paris is the capital city of France."),
        ("Capital of France", "Python is a programming language."),
    ]

    for query, doc in test_pairs:
        start = time.time()
        score = get_score(url, model, query, doc)
        latency = (time.time() - start) * 1000

        if score is not None:
            print(f"  ✓ Score: {score:.4f} (latency: {latency:.1f}ms)")
            print(f"    Query: {query}")
            print(f"    Doc: {doc[:50]}...")
        else:
            print(f"  ✗ Failed to score")
            print(f"    Query: {query}")

    # Test 3: Ranking test
    print("\n[Test 3] Document Ranking Test")
    print("-" * 40)

    query = "What is machine learning?"
    documents = [
        "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
        "The Eiffel Tower is located in Paris, France.",
        "Deep learning uses neural networks with many layers to process data.",
        "The stock market opened higher today after positive economic news.",
        "Supervised learning requires labeled training data to make predictions.",
    ]

    print(f"  Query: {query}")
    print(f"  Documents to rank: {len(documents)}")
    print()

    ranked = rerank_documents(url, model, query, documents)

    if ranked:
        print("  Ranking results (highest relevance first):")
        for rank, (orig_idx, score, doc) in enumerate(ranked, 1):
            print(f"    {rank}. [score: {score:.4f}] {doc[:60]}...")

        # Check if relevant docs ranked higher
        # Docs 0, 2, 4 should be ranked higher than 1, 3
        relevant_indices = {0, 2, 4}
        top_3_orig = {r[0] for r in ranked[:3]}

        relevant_in_top_3 = len(relevant_indices & top_3_orig)
        print(f"\n  Relevant documents in top 3: {relevant_in_top_3}/3")

        if relevant_in_top_3 >= 2:
            print("  ✓ Ranking quality: GOOD")
        else:
            print("  ⚠ Ranking quality: NEEDS REVIEW")
    else:
        print("  ✗ Ranking failed")

    # Test 4: Throughput
    print("\n[Test 4] Throughput Test")
    print("-" * 40)

    start = time.time()
    success = 0
    for i in range(10):
        if get_score(url, model, "Test query", f"Test document {i}"):
            success += 1

    elapsed = time.time() - start
    throughput = success / elapsed
    print(f"  Successful requests: {success}/10")
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Throughput: {throughput:.2f} req/s")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="Test vLLM reranker quality")
    parser.add_argument("--url", required=True, help="vLLM server URL")
    parser.add_argument("--model", required=True, help="Model name")

    args = parser.parse_args()

    success = run_tests(args.url, args.model)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

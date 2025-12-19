#!/usr/bin/env python3
"""
Test embedding quality by comparing vLLM outputs to sentence-transformers baseline.

Usage:
    python test_embedding_quality.py --url <vllm-url> --model <model-name> [--baseline]

Examples:
    # Test MiniLM
    python test_embedding_quality.py \
        --url https://minilm-embedding-vllm-embeddings.apps.cluster.local \
        --model sentence-transformers/all-MiniLM-L6-v2 \
        --baseline

    # Test Granite
    python test_embedding_quality.py \
        --url https://granite-embedding-vllm-embeddings.apps.cluster.local \
        --model ibm-granite/granite-embedding-278m-multilingual
"""

import argparse
import json
import sys
import time
from typing import Optional

import numpy as np
import requests

# Suppress SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_vllm_embedding(url: str, model: str, text: str) -> Optional[list[float]]:
    """Get embedding from vLLM server."""
    try:
        response = requests.post(
            f"{url}/v1/embeddings",
            json={"input": text, "model": model},
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"Error getting vLLM embedding: {e}")
        return None


def get_baseline_embedding(model: str, text: str) -> Optional[list[float]]:
    """Get embedding from sentence-transformers (baseline)."""
    try:
        from sentence_transformers import SentenceTransformer
        st_model = SentenceTransformer(model)
        embedding = st_model.encode(text)
        return embedding.tolist()
    except ImportError:
        print("sentence-transformers not installed. Run: pip install sentence-transformers")
        return None
    except Exception as e:
        print(f"Error getting baseline embedding: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def run_tests(url: str, model: str, compare_baseline: bool = False):
    """Run embedding quality tests."""

    test_texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a branch of artificial intelligence.",
        "Paris is the capital of France.",
        "Climate change is affecting global weather patterns.",
        "Python is a popular programming language.",
    ]

    similar_pairs = [
        ("Machine learning enables computers to learn from data.",
         "AI systems can improve through experience without explicit programming."),
        ("The stock market crashed yesterday.",
         "Financial markets experienced a significant downturn."),
    ]

    dissimilar_pairs = [
        ("The weather is sunny today.",
         "Quantum computing uses qubits for calculation."),
        ("I love pizza.",
         "The GDP of Japan is 5 trillion dollars."),
    ]

    print("=" * 60)
    print(f"vLLM Embedding Quality Test")
    print(f"URL: {url}")
    print(f"Model: {model}")
    print("=" * 60)

    # Test 1: Basic embedding generation
    print("\n[Test 1] Basic Embedding Generation")
    print("-" * 40)

    embeddings = []
    for i, text in enumerate(test_texts):
        start = time.time()
        emb = get_vllm_embedding(url, model, text)
        latency = (time.time() - start) * 1000

        if emb:
            embeddings.append(emb)
            print(f"  [{i+1}] ✓ Dimension: {len(emb)}, Latency: {latency:.1f}ms")
        else:
            print(f"  [{i+1}] ✗ Failed")

    if not embeddings:
        print("\n❌ FAILED: No embeddings generated")
        return False

    # Verify dimensions
    expected_dims = {"all-MiniLM-L6-v2": 384, "granite-embedding-278m": 768}
    model_short = model.split("/")[-1]
    if model_short in expected_dims:
        actual_dim = len(embeddings[0])
        expected = expected_dims[model_short]
        if actual_dim == expected:
            print(f"\n✓ Dimension check passed: {actual_dim}")
        else:
            print(f"\n✗ Dimension mismatch: got {actual_dim}, expected {expected}")

    # Test 2: Similarity tests
    print("\n[Test 2] Semantic Similarity (similar pairs should score > 0.7)")
    print("-" * 40)

    for text1, text2 in similar_pairs:
        emb1 = get_vllm_embedding(url, model, text1)
        emb2 = get_vllm_embedding(url, model, text2)

        if emb1 and emb2:
            sim = cosine_similarity(emb1, emb2)
            status = "✓" if sim > 0.7 else "✗"
            print(f"  {status} Similarity: {sim:.4f}")
            print(f"    Text 1: {text1[:50]}...")
            print(f"    Text 2: {text2[:50]}...")
        else:
            print("  ✗ Failed to get embeddings")

    print("\n[Test 3] Semantic Dissimilarity (dissimilar pairs should score < 0.5)")
    print("-" * 40)

    for text1, text2 in dissimilar_pairs:
        emb1 = get_vllm_embedding(url, model, text1)
        emb2 = get_vllm_embedding(url, model, text2)

        if emb1 and emb2:
            sim = cosine_similarity(emb1, emb2)
            status = "✓" if sim < 0.5 else "⚠"
            print(f"  {status} Similarity: {sim:.4f}")
            print(f"    Text 1: {text1[:50]}...")
            print(f"    Text 2: {text2[:50]}...")
        else:
            print("  ✗ Failed to get embeddings")

    # Test 3: Compare to baseline
    if compare_baseline:
        print("\n[Test 4] Baseline Comparison (vLLM vs sentence-transformers)")
        print("-" * 40)

        for text in test_texts[:2]:
            vllm_emb = get_vllm_embedding(url, model, text)
            baseline_emb = get_baseline_embedding(model, text)

            if vllm_emb and baseline_emb:
                sim = cosine_similarity(vllm_emb, baseline_emb)
                status = "✓" if sim > 0.99 else "⚠" if sim > 0.95 else "✗"
                print(f"  {status} Match score: {sim:.6f}")
                print(f"    Text: {text[:50]}...")

                if sim < 0.99:
                    print(f"    ⚠ Warning: Embeddings differ from baseline")
            else:
                print(f"  ✗ Failed comparison for: {text[:50]}...")

    # Test 4: Throughput
    print("\n[Test 5] Throughput Test (10 requests)")
    print("-" * 40)

    start = time.time()
    success = 0
    for _ in range(10):
        if get_vllm_embedding(url, model, "Test sentence for throughput measurement."):
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
    parser = argparse.ArgumentParser(description="Test vLLM embedding quality")
    parser.add_argument("--url", required=True, help="vLLM server URL")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--baseline", action="store_true",
                        help="Compare against sentence-transformers baseline")

    args = parser.parse_args()

    success = run_tests(args.url, args.model, args.baseline)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

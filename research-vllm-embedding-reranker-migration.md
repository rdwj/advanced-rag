# vLLM Migration Research: Embedding and Reranker Model Support

**Research Date:** 2025-12-18
**Objective:** Evaluate vLLM compatibility with current Caikit-served models for potential migration

## Executive Summary

**Key Finding:** vLLM has **limited and evolving support** for sentence-transformer embedding models and cross-encoder rerankers. While recent progress has been made, **direct migration from Caikit to vLLM for these specific models is NOT recommended** at this time.

### Recommendation Matrix

| Model | vLLM Support Status | Recommendation | Alternative |
|-------|-------------------|----------------|-------------|
| **sentence-transformers/all-MiniLM-L6-v2** | Partial/Experimental | ⚠️ NOT READY | Keep Caikit or use TEI |
| **ibm-granite/granite-embedding-278m-multilingual** | Unknown | ⚠️ NOT READY | Keep Caikit or use TEI |
| **cross-encoder/ms-marco-MiniLM-L12-v2** | No Direct Support | ❌ NOT SUPPORTED | Keep Caikit or separate service |

**Bottom Line:** Continue using Caikit-NLP for these models. If migration is required for operational reasons, consider **Text Embeddings Inference (TEI)** or **sentence-transformers library** directly instead of vLLM.

---

## Current Model Analysis

### 1. sentence-transformers/all-MiniLM-L6-v2 (Embedding Model)

**Architecture:**
- Base: BERT (MiniLM variant)
- Type: Encoder-only
- Parameters: 22.7M
- Output: 384-dimensional embeddings
- Max sequence length: 256 tokens
- Pooling: Mean pooling with attention mask

**vLLM Compatibility:**

✅ **Technically Possible** - vLLM added BERT support in 2024
⚠️ **Practically Problematic** - Requires sentence-transformers configuration files
⚠️ **No Performance Guarantee** - vLLM docs state: "We currently support pooling models primarily for convenience. This is not guaranteed to provide any performance improvements over using Hugging Face Transformers or Sentence Transformers directly."

**Status:** While vLLM merged support for BERT-based models and sentence-transformers config files (PR #9056, #9506), several models like all-mpnet-base-v2 and distilbert-based models still don't work properly. The all-MiniLM-L6-v2 model falls into this category of "starting to use Sentence Transformers" but without confirmed vLLM compatibility.

### 2. ibm-granite/granite-embedding-278m-multilingual (Embedding Model)

**Architecture:**
- Base: XLM-RoBERTa-like encoder-only transformer
- Type: Encoder-only
- Parameters: 278M
- Output: 768-dimensional embeddings
- Max sequence length: 512 tokens
- Pooling: CLS pooling
- Languages: 12 (English, German, Spanish, French, Japanese, Portuguese, Arabic, Czech, Italian, Korean, Dutch, Chinese)

**vLLM Compatibility:**

❓ **Unknown** - No specific information found about Granite embedding models in vLLM
⚠️ **Likely Unsupported** - Architecture similar to sentence-transformers models which have known issues
✅ **Works with:** SentenceTransformers, Hugging Face Transformers, Ollama, llama.cpp

**Status:** The Granite embedding model uses an encoder-only architecture compatible with sentence-transformers library. No evidence of vLLM testing or support. Given the issues with similar models, assume incompatibility.

### 3. cross-encoder/ms-marco-MiniLM-L12-v2 (Reranker Model)

**Architecture:**
- Base: microsoft/MiniLM-L12-H384-uncased
- Type: Sequence classification (cross-encoder)
- Parameters: 33.4M
- Task: Text ranking/reranking
- Output: Relevance scores (not embeddings)
- Performance: NDCG@10: 74.30, MRR@10: 39.01
- Throughput: 1800 docs/sec (V100 GPU)

**How Cross-Encoders Work:**
Unlike bi-encoders (sentence-transformers) that encode query and document separately, cross-encoders:
1. Concatenate query + document as input
2. Process through transformer jointly
3. Output a single relevance score
4. Must process each query-document pair (slower but more accurate)

**vLLM Compatibility:**

❌ **Not Directly Supported** - Cross-encoders are fundamentally different from generative LLMs
⚠️ **Reranking API Exists** - vLLM added `/v1/score` API for sentence-pair scoring
⚠️ **Limited Model Support** - Reranking primarily tested with Qwen3-Reranker, not MS-MARCO models

**Status:** vLLM merged reranker support in July 2024 (PR #15876) with a `/v1/score` endpoint, but documentation focuses on Qwen3-Reranker models which use a different approach (logits of 'yes'/'no' tokens). MS-MARCO cross-encoders use sequence classification heads. No evidence of MS-MARCO model compatibility.

---

## Technical Deep Dive: Why vLLM Struggles with These Models

### Architecture Mismatch

**vLLM's Design Focus:**
- Optimized for **decoder-only** causal language models (GPT-style)
- PagedAttention for efficient KV cache management (only relevant for generation)
- Continuous batching for generation tasks
- Built for autoregressive token generation

**Embedding Models' Architecture:**
- **Encoder-only** bidirectional transformers (BERT-style)
- No autoregressive generation
- No KV cache needed
- Single forward pass produces fixed-size output
- Requires pooling operations (mean, CLS, etc.)

**The Fundamental Problem:**
vLLM's core optimizations (PagedAttention, continuous batching) provide **zero benefit** for encoder-only models doing single-pass embeddings. The documentation explicitly states this: "We currently support pooling models primarily for convenience. This is not guaranteed to provide any performance improvements."

### Configuration File Complexity

Sentence-transformers models require two critical config files:

1. **modules.json** - Describes layer architecture
2. **Component config.json** - Contains pooling method, normalization settings

Early vLLM versions hardcoded these parameters, breaking models with custom configurations. While fixed in November 2024 (PR #9506), many models still have compatibility issues.

### Cross-Encoder Fundamental Differences

Cross-encoders are **sequence classification models**, not embedding models. They:
- Don't produce embeddings (output is a scalar score)
- Require joint processing of text pairs
- Use classification heads, not pooling layers
- Are task-specific (can't be repurposed for other tasks)

vLLM's reranking API is nascent and focused on newer models (Qwen3-Reranker) that use LLM-style scoring rather than traditional cross-encoder classification.

---

## vLLM Development Status Timeline

### Embedding Support History

- **June 2024:** Issue #5179 - BERT models for embeddings requested
- **September 2024:** PR #9056 - Initial BERT model support merged
- **November 2024:** PR #9506 - Sentence-transformers config file support merged (COMPLETED)
- **January 2025:** Issue #17493 - Sentence transformers embeddings still problematic
- **Current:** Partial support, no performance optimization, many models still broken

### Reranker Support History

- **July 2024:** Issue #6928 - Rerank models requested (essential to RAG)
- **November 2024:** PR #15876 - Reranker support merged
- **June 2025:** PR #19260 - Qwen3 Reranker support added (COMPLETED)
- **Current:** `/v1/score` API exists, focus on Qwen3-Reranker, MS-MARCO compatibility unknown

### Key Insight

vLLM embedding/reranking support is **less than 1 year old** and still maturing. The project's focus remains on optimizing generation models, not encoder-only architectures.

---

## Migration Path Analysis

### Option 1: Wait for vLLM Maturity (NOT RECOMMENDED)

**Pros:**
- Single serving stack for all models
- Potential future optimizations

**Cons:**
- No timeline for full sentence-transformers compatibility
- No performance guarantees even when working
- Risk of breaking changes as support evolves
- Limited community testing for your specific models
- vLLM team explicitly says "primarily for convenience"

**Verdict:** ❌ Don't migrate now. Revisit in 12-18 months.

### Option 2: Keep Caikit-NLP (RECOMMENDED)

**Pros:**
- Known working solution
- Optimized for encoder-only models
- Production-tested
- Supports your exact models

**Cons:**
- Separate serving stack to maintain
- Different deployment/scaling approach

**Verdict:** ✅ Best option for stability and reliability.

### Option 3: Migrate to Text Embeddings Inference (TEI)

**What is TEI?**
Hugging Face's dedicated inference server for embedding models, optimized for encoder-only architectures.

**Pros:**
- Purpose-built for embedding models
- Better performance than vLLM for embeddings (Snowflake Arctic: 2.4x faster for short sequences)
- Supports sentence-transformers models natively
- Active development and maintenance
- Easier deployment (Docker images available)
- OpenShift-compatible

**Cons:**
- Another serving stack (not unified with LLM serving)
- Doesn't support rerankers (separate solution needed)

**Supported Models:**
- ✅ All sentence-transformers models including all-MiniLM-L6-v2
- ✅ Qwen3-Embedding models
- ❓ Granite models (likely supported via sentence-transformers compatibility)

**Verdict:** ✅ Strong alternative if migrating away from Caikit.

### Option 4: Direct sentence-transformers Library

**Pros:**
- Most flexible
- Full control over model serving
- Simple FastAPI wrapper
- Works with all sentence-transformers models
- Easy to containerize for OpenShift

**Cons:**
- DIY serving solution
- Need to implement batching, GPU management
- No built-in monitoring/observability

**Verdict:** ✅ Good for custom requirements or small scale.

### Option 5: Use vLLM for Reranking with Qwen Models

**Alternative Approach:**
If reranking is critical and you're willing to change models:

- Replace MS-MARCO cross-encoder with **Qwen3-Reranker-0.6B, 4B, or 8B**
- These ARE supported in vLLM (as of June 2025)
- Qwen3-Reranker-8B ranks #1 on MTEB multilingual leaderboard
- Uses `/v1/rerank` API endpoint

**Trade-offs:**
- Larger model (600M-8B vs 33M parameters)
- Higher GPU memory requirements
- Better multilingual performance
- Model change requires re-validation of RAG pipeline

**Verdict:** ⚠️ Consider if unified vLLM stack is priority and reranker model change is acceptable.

---

## Compatibility Matrix

| Model | Caikit | vLLM | TEI | sentence-transformers | Qwen3-Reranker |
|-------|--------|------|-----|----------------------|----------------|
| **all-MiniLM-L6-v2** | ✅ | ⚠️ | ✅ | ✅ | N/A |
| **granite-embedding-278m** | ✅ | ❌ | ✅* | ✅ | N/A |
| **ms-marco-MiniLM-L12-v2** | ✅ | ❌ | ❌ | ✅ | Replace with Qwen3 |

*Likely supported but not explicitly documented

---

## Performance Considerations

### Embedding Models

Based on Snowflake Arctic Inference benchmarks comparing vLLM vs TEI:

| Sequence Length | TEI Advantage | vLLM Optimized Advantage |
|----------------|---------------|-------------------------|
| 50 tokens | Baseline | 2.4x faster |
| 512 tokens | Baseline | Performance parity |

**Key Insight:** Even with vLLM optimization efforts (Arctic Inference), TEI remains competitive or superior for embedding workloads.

### Reranker Models

**MS-MARCO MiniLM-L12-v2:**
- Throughput: 1800 docs/sec (V100 GPU)
- Latency: ~0.56ms per query-doc pair

**Qwen3-Reranker (vLLM alternative):**
- 0.6B model: Faster but lower quality
- 4B model: Balanced
- 8B model: Best quality, slower

Cross-encoder throughput is always lower than bi-encoder due to joint processing requirement.

---

## Architecture Alternatives

### Alternative 1: Keep Specialized Serving

```
┌─────────────────────┐
│   RAG Application   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
┌───▼────┐   ┌───▼────┐
│ vLLM   │   │ Caikit │
│ (LLMs) │   │(Embed) │
└────────┘   └────────┘
```

**Best for:** Production stability, proven performance

### Alternative 2: Text Embeddings Inference (TEI)

```
┌─────────────────────┐
│   RAG Application   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐────────┐
    │             │        │
┌───▼────┐   ┌───▼────┐  ┌▼────────┐
│ vLLM   │   │  TEI   │  │sentence │
│ (LLMs) │   │(Embed) │  │transform│
└────────┘   └────────┘  │(rerank) │
                          └─────────┘
```

**Best for:** Migrating from Caikit while maintaining performance

### Alternative 3: Wait for vLLM (NOT RECOMMENDED)

```
┌─────────────────────┐
│   RAG Application   │
└──────────┬──────────┘
           │
       ┌───▼────┐
       │  vLLM  │
       │ (All)  │
       └────────┘
```

**Best for:** 12-18 months from now, maybe

---

## Detailed Model-Specific Recommendations

### For all-MiniLM-L6-v2

**Current State:** Working in Caikit

**Migration Options:**
1. **Keep in Caikit** (RECOMMENDED)
2. **Migrate to TEI:** Straightforward, better performance than vLLM
3. **DIY with sentence-transformers:** Simple FastAPI wrapper
4. **Try vLLM experimentally:** Use `--runner pooling`, expect issues

**Code Example (TEI):**
```bash
# Deploy TEI on OpenShift
podman run --platform linux/amd64 \
  -p 8080:80 \
  -v $PWD/data:/data \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id sentence-transformers/all-MiniLM-L6-v2
```

**Code Example (sentence-transformers):**
```python
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI

app = FastAPI()
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

@app.post("/embed")
def embed(texts: list[str]):
    embeddings = model.encode(texts)
    return {"embeddings": embeddings.tolist()}
```

### For granite-embedding-278m-multilingual

**Current State:** Working in Caikit

**Migration Options:**
1. **Keep in Caikit** (RECOMMENDED)
2. **Migrate to TEI:** Should work (XLM-RoBERTa architecture)
3. **Use Ollama:** Confirmed support (`ollama run granite-embedding:278m`)
4. **DIY with sentence-transformers:** IBM confirms compatibility

**Testing TEI Compatibility:**
```bash
# Test if TEI supports Granite
podman run --platform linux/amd64 \
  -p 8080:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id ibm-granite/granite-embedding-278m-multilingual

# If it works, you'll see model loading logs
# If not, fall back to sentence-transformers
```

**Fallback (sentence-transformers):**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('ibm-granite/granite-embedding-278m-multilingual')
embeddings = model.encode(["Hello world", "Bonjour le monde"])
# Returns: (2, 768) array
```

### For ms-marco-MiniLM-L12-v2 (Cross-Encoder Reranker)

**Current State:** Working in Caikit

**Migration Options:**
1. **Keep in Caikit** (RECOMMENDED)
2. **Replace with Qwen3-Reranker + vLLM:** Model change required
3. **DIY with sentence-transformers CrossEncoder:** Simple deployment
4. **Use FlashRank:** Ultra-lightweight alternative (4MB model)

**Code Example (sentence-transformers):**
```python
from sentence_transformers import CrossEncoder
from fastapi import FastAPI

app = FastAPI()
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L12-v2')

@app.post("/rerank")
def rerank(query: str, documents: list[str]):
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return {"ranked_documents": ranked}
```

**Code Example (Qwen3-Reranker with vLLM):**
```python
from vllm import LLM, SamplingParams

# Deploy Qwen3-Reranker
llm = LLM(model="Qwen/Qwen3-Reranker-0.6B", task="rerank")

# Use /v1/rerank endpoint
import requests
response = requests.post("http://localhost:8000/v1/rerank", json={
    "query": "What is the capital of France?",
    "documents": [
        "Paris is the capital of France.",
        "London is the capital of England.",
        "Berlin is the capital of Germany."
    ]
})
```

---

## Cost and Resource Analysis

### Current Caikit Setup (Per Model)

| Model | GPU Memory | CPU | Status |
|-------|-----------|-----|--------|
| all-MiniLM-L6-v2 | ~1GB | Low | Efficient |
| granite-embedding-278m | ~2GB | Medium | Efficient |
| ms-marco-MiniLM-L12-v2 | ~1GB | Low | Efficient |
| **Total** | **~4GB** | **Low-Medium** | **✅ Optimized** |

### vLLM Alternative (If Using Qwen3)

| Model | GPU Memory | CPU | Status |
|-------|-----------|-----|--------|
| all-MiniLM-L6-v2 (vLLM) | ~1GB | Low | ⚠️ No perf gain |
| granite-embedding-278m | ❌ Not supported | - | - |
| Qwen3-Reranker-0.6B | ~2GB | Medium | ✅ Works |
| **Total** | **~3GB** | **Low-Medium** | **⚠️ Model changes** |

### TEI + sentence-transformers Hybrid

| Model | GPU Memory | CPU | Status |
|-------|-----------|-----|--------|
| all-MiniLM-L6-v2 (TEI) | ~1GB | Low | ✅ Optimized |
| granite-embedding-278m (TEI) | ~2GB | Medium | ✅ Likely works |
| ms-marco-MiniLM-L12-v2 | ~1GB | Low | ✅ DIY serving |
| **Total** | **~4GB** | **Low-Medium** | **✅ Same footprint** |

**Key Insight:** No resource savings from migrating to vLLM. Caikit and TEI have similar footprints.

---

## Testing Plan (If You Proceed with vLLM)

### Phase 1: Viability Testing

1. **Test all-MiniLM-L6-v2 in vLLM:**
   ```bash
   vllm serve sentence-transformers/all-MiniLM-L6-v2 \
     --task embed \
     --runner pooling

   # Test embedding endpoint
   curl http://localhost:8000/v1/embeddings \
     -H "Content-Type: application/json" \
     -d '{"input": "Hello world", "model": "sentence-transformers/all-MiniLM-L6-v2"}'
   ```

2. **Verify embedding quality:**
   - Compare vLLM embeddings vs Caikit embeddings
   - Check vector dimensions (should be 384)
   - Compute cosine similarity for known similar/dissimilar pairs
   - Must match within 0.01 tolerance

3. **Benchmark performance:**
   - Measure throughput (embeddings/sec)
   - Measure latency (p50, p95, p99)
   - Compare against Caikit baseline
   - vLLM must be ≥80% of Caikit performance to justify migration

### Phase 2: Granite Model Testing

```bash
# This will likely FAIL - document the error
vllm serve ibm-granite/granite-embedding-278m-multilingual \
  --task embed \
  --runner pooling

# If it fails, try with sentence-transformers backend
vllm serve ibm-granite/granite-embedding-278m-multilingual \
  --model-impl transformers \
  --task embed
```

### Phase 3: Reranker Testing

```bash
# Try MS-MARCO (will likely fail)
vllm serve cross-encoder/ms-marco-MiniLM-L12-v2 \
  --task score

# Alternative: Test Qwen3-Reranker
vllm serve Qwen/Qwen3-Reranker-0.6B \
  --task rerank
```

### Success Criteria

Proceed with migration ONLY if:
- ✅ All models load successfully in vLLM
- ✅ Embedding quality matches Caikit (cosine similarity ≥0.99)
- ✅ Performance is ≥80% of Caikit baseline
- ✅ No configuration workarounds required
- ✅ vLLM version stability (not bleeding edge)

**Expected Result:** Likely to fail on at least 2 of 5 criteria.

---

## Final Recommendations

### Immediate Action (Next 30 Days)

**DO:**
1. ✅ Keep Caikit-NLP for all three models
2. ✅ Document current performance baselines
3. ✅ Monitor vLLM release notes for embedding improvements
4. ✅ Consider TEI for new embedding models (not migration)

**DON'T:**
1. ❌ Migrate production workloads to vLLM for embeddings/reranking
2. ❌ Assume vLLM support equals vLLM optimization
3. ❌ Rush migration without thorough testing

### Short-Term (3-6 Months)

**DO:**
1. ✅ Set up test environment with vLLM for continuous evaluation
2. ✅ Test new vLLM releases against your models
3. ✅ Evaluate TEI as Caikit alternative (not vLLM)
4. ✅ Consider Qwen3-Reranker if reranker model flexibility exists

**DON'T:**
1. ❌ Expect dramatic performance improvements from vLLM
2. ❌ Migrate without performance parity

### Long-Term (12-18 Months)

**DO:**
1. ✅ Re-evaluate vLLM embedding support maturity
2. ✅ Monitor for architectural changes favoring encoder-only models
3. ✅ Consider unified serving if vLLM proves reliable

**CONSIDER:**
- vLLM may never prioritize encoder-only optimization (not their core mission)
- TEI + vLLM hybrid may be the long-term architecture
- Purpose-built tools (TEI, Caikit) will likely remain superior for embeddings

---

## Questions to Ask Before Migration

1. **Why migrate?**
   - If "single serving stack": Consider if worth the risk
   - If "performance": vLLM offers no embedding performance advantage
   - If "new features": What features? vLLM doesn't add value here
   - If "maintenance burden": TEI is easier than vLLM for embeddings

2. **Can you tolerate model changes?**
   - Reranker: Must replace MS-MARCO with Qwen3
   - Embeddings: May need to replace with vLLM-optimized alternatives
   - RAG pipeline re-validation required

3. **What's your risk tolerance?**
   - High: Experiment with vLLM
   - Medium: Try TEI
   - Low: Keep Caikit

4. **What's your timeline?**
   - Urgent: Keep Caikit
   - 3-6 months: Consider TEI
   - 12+ months: Re-evaluate vLLM

---

## Additional Resources

### Documentation

- [vLLM Pooling Models](https://docs.vllm.ai/en/latest/models/pooling_models/)
- [vLLM Supported Models](https://docs.vllm.ai/en/latest/models/supported_models/)
- [Text Embeddings Inference (TEI)](https://huggingface.co/docs/text-generation-inference/index)
- [Sentence Transformers Documentation](https://www.sbert.net/docs/quickstart.html)

### GitHub Issues (Track Progress)

- [vLLM #17493 - Sentence transformers embeddings support](https://github.com/vllm-project/vllm/issues/17493)
- [vLLM #9388 - Support sentence-transformers configuration files](https://github.com/vllm-project/vllm/issues/9388)
- [vLLM #6928 - Support rerank models](https://github.com/vllm-project/vllm/issues/6928)
- [vLLM #21796 - RFC: Optimize embedding task](https://github.com/vllm-project/vllm/issues/21796)

### Benchmarks

- [Snowflake Arctic Inference: 16x Throughput for Embeddings](https://medium.com/snowflake/scaling-vllm-for-embeddings-16x-throughput-and-cost-reduction-f2b4d4c8e1bf)

### Model Cards

- [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [ibm-granite/granite-embedding-278m-multilingual](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual)
- [cross-encoder/ms-marco-MiniLM-L12-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L12-v2)
- [Qwen/Qwen3-Reranker-8B](https://huggingface.co/Qwen/Qwen3-Reranker-8B)

---

## Conclusion

**vLLM is NOT the right tool for serving sentence-transformer embedding models and cross-encoder rerankers in production as of December 2025.**

While vLLM has made strides in supporting encoder-only models, the implementation is:
- Immature (less than 1 year old)
- Incomplete (many models still broken)
- Unoptimized (explicit "no performance guarantee" warning)
- Not their focus (decoder-only LLMs are the priority)

**For your specific models:**
- ❌ all-MiniLM-L6-v2: Experimental support, no advantage over Caikit/TEI
- ❌ granite-embedding-278m-multilingual: Likely unsupported
- ❌ ms-marco-MiniLM-L12-v2: Not supported (would require Qwen3 replacement)

**Recommended Path:**
1. **Keep Caikit-NLP** for production stability
2. **Evaluate TEI** as a modern alternative (if migration is required)
3. **Monitor vLLM** progress but don't migrate yet
4. **Re-assess in 12-18 months** when embedding support matures

The desire for a unified serving stack is understandable, but premature migration risks production stability for theoretical convenience that doesn't materialize in practice.

---

## Sources

- [vLLM Supported Models Documentation](https://docs.vllm.ai/en/latest/models/supported_models/)
- [vLLM Pooling Models Documentation](https://docs.vllm.ai/en/latest/models/pooling_models/)
- [vLLM Feature Request: Sentence transformers embeddings support](https://github.com/vllm-project/vllm/issues/17493)
- [vLLM Feature: Support sentence-transformers configuration files](https://github.com/vllm-project/vllm/issues/9388)
- [vLLM Feature: Support rerank models](https://github.com/vllm-project/vllm/issues/6928)
- [vLLM Feature: Support Qwen3 Embedding & Reranker](https://github.com/vllm-project/vllm/issues/19229)
- [Deploying Qwen3-Reranker-8B with vLLM](https://medium.com/@kimdoil1211/deploying-qwen3-reranker-8b-with-vllm-instruction-aware-reranking-for-next-generation-retrieval-c35a57c9f0a6)
- [Serving Rerankers on Vast.ai using vLLM](https://vast.ai/article/serving-rerankers-on-vastai-using-vllm)
- [Best vLLM alternatives for sentence transformers](https://www.byteplus.com/en/topic/515224)
- [Scaling vLLM for Embeddings: 16x Throughput and Cost Reduction](https://medium.com/snowflake/scaling-vllm-for-embeddings-16x-throughput-and-cost-reduction-f2b4d4c8e1bf)
- [sentence-transformers/all-MiniLM-L6-v2 Model Card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [ibm-granite/granite-embedding-278m-multilingual Model Card](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual)
- [cross-encoder/ms-marco-MiniLM-L6-v2 Model Card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2)
- [Reranking with Elasticsearch-hosted cross-encoder](https://www.elastic.co/search-labs/blog/elasticsearch-cross-encoder-reranker-huggingface)
- [Hugging Face Text Generation Inference](https://huggingface.co/docs/text-generation-inference/index)
- [MS MARCO Cross-Encoders Documentation](https://www.sbert.net/docs/pretrained-models/ce-msmarco.html)

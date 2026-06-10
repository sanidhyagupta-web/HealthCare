# Skill: Hybrid Search

## What this covers
The full retrieval path: vector search + BM25, RRF merge, cross-encoder rerank, role filtering.

## Retrieval pipeline (in order)

### 1. Vector retrieval
`indexing/chroma_store.py` — query Chroma with the embedded query, return top 20 candidates with metadata.

```python
from indexing.chroma_store import query_chunks
from indexing.embeddings import embed_texts

query_embedding = embed_texts([query])[0]
vector_results = query_chunks(query_embedding, n_results=20)
# Returns: [{"chunk_id": ..., "text": ..., "score": ..., "metadata": {...}}, ...]
```

### 2. Keyword retrieval
BM25 index at `data/bm25_index.json`, loaded by `KeywordIndexWorker` via `rank_bm25.BM25Okapi`.

```python
from rank_bm25 import BM25Okapi
# Load index, tokenize query, get top 20 chunk IDs and scores
```

### 3. RRF merge
Reciprocal Rank Fusion — 60% weight on vector rank, 40% on keyword rank:

```python
def rrf_merge(vector_results, keyword_results, alpha=0.6):
    scores = {}
    for rank, result in enumerate(vector_results):
        cid = result["chunk_id"]
        scores[cid] = scores.get(cid, 0) + alpha * (1 / (rank + 1))
    for rank, result in enumerate(keyword_results):
        cid = result["chunk_id"]
        scores[cid] = scores.get(cid, 0) + (1 - alpha) * (1 / (rank + 1))
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

Do NOT change `alpha` without updating `evaluation/run_eval.py` and re-running evals.

### 4. Cross-encoder rerank
`indexing/reranker.py` — model `cross-encoder/ms-marco-MiniLM-L-6-v2`. Pass top-20 RRF candidates, return top 5.

```python
from indexing.reranker import rerank
top5 = rerank(query=query, candidates=rrf_top20, top_k=5)
```

### 5. Role-based filtering
`security/access_control.py:filter_results_by_role(results, user_role)` — must be called **before** passing results to the LLM. Removes chunks whose `allowed_roles` don't include the caller's role.

```python
from security.access_control import filter_results_by_role
filtered = filter_results_by_role(top5, user_role=current_user.role)
```

### 6. Audit log
Log the query event **after** filtering, **before** calling the LLM. See `skills/audit-logging.md`.

## Bad examples

```python
# BAD: vector-only retrieval
results = query_chunks(query_embedding, n_results=5)
return generate_answer(query, results)  # no keyword, no rerank, no RBAC

# BAD: filtering after LLM call
answer = generate_answer(query, top5)
filtered = filter_results_by_role(top5, role)  # too late — LLM already saw forbidden chunks

# BAD: hardcoded alpha
scores[cid] += 0.7 * (1 / rank)  # diverges from eval baseline
```

## Failure modes seen
- Agent adds vector-only retrieval and skips BM25 — fails on short queries and rare ICD-10 codes.
- Agent filters results *after* LLM generation — LLM has already seen PHI the caller isn't allowed to view.
- Agent forgets to audit-log the query — compliance gap.

## Must NOT do
- Return results without `filter_results_by_role`.
- Skip the cross-encoder step for "performance" reasons without documenting it.
- Change RRF alpha without updating evals.
- Pass unfiltered results to `llm/claude_client.py`.

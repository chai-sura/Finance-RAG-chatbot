"""
reranker.py — cross-encoder reranking.

The vector search (bi-encoder) is fast but imprecise: it scores query and
chunk separately. A cross-encoder reads (query, chunk) TOGETHER and scores
true relevance — more accurate, but slower, so we run it only on the
shortlist the vector search already produced.

Flow: retrieve ~20 candidates (wide net) -> rerank -> keep top N.
"""

from sentence_transformers import CrossEncoder

MODEL_NAME = "BAAI/bge-reranker-base"

# Load once at import (downloads ~1GB the first time, then cached).
_model = CrossEncoder(MODEL_NAME)


def rerank(query: str, candidates: list, top_n: int = 5) -> list:
    """Re-score candidates against the query, return the top_n.

    candidates: list of (document_text, metadata) tuples.
    Returns the same tuple shape, reordered, truncated to top_n.
    """
    if not candidates:
        return []

    # The cross-encoder scores each (query, document) pair.
    pairs = [(query, doc) for doc, _meta in candidates]
    scores = _model.predict(pairs)

    # Pair each candidate with its score, sort high-to-low, keep top_n.
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [cand for _score, cand in ranked[:top_n]]


if __name__ == "__main__":
    # Quick self-test: rerank a few toy candidates and watch the order.
    cands = [
        ("FinSolve was founded in 2018 in Bangalore.", {"source": "a"}),
        ("The marketing campaign ran in Q3 2024.", {"source": "b"}),
        ("FinSolve's headquarters is located in Bangalore, India.", {"source": "c"}),
    ]
    out = rerank("Where is FinSolve headquartered?", cands, top_n=3)
    print("Reranked order:")
    for doc, meta in out:
        print(f"  [{meta['source']}] {doc}")
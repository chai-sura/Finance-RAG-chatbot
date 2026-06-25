"""
embeddings.py — Phase 1, Step 2.

Job: turn text into vectors (lists of numbers that capture meaning).
This is what makes semantic search possible. Two chunks with similar
meaning produce similar vectors; we measure "relevance" as vector closeness.

We use BAAI/bge-small-en-v1.5, a small, high-quality retrieval model.
"""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE was trained so that QUERIES get a short instruction prefix, but
# DOCUMENTS do not. Skipping this on queries noticeably hurts retrieval
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Load the model once at import time. The first run downloads it from the HuggingFace Hub
# after that it's cached locally and loads fast.
_model = SentenceTransformer(MODEL_NAME)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunk texts (no prefix). Used at ingestion time."""
    # normalize_embeddings=True scales every vector to length 1, which makes
    # cosine similarity behave cleanly, important for consistent retrieval.
    embeddings = _model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single user question (WITH the BGE prefix). Used at query time."""
    embedding = _model.encode(QUERY_PREFIX + text, normalize_embeddings=True)
    return embedding.tolist()

if __name__ == "__main__":
    sample = "FinSolve is a fintech company based in Bangalore."
    vec = embed_documents([sample])[0]
    print(f"Model: {MODEL_NAME}")
    print(f"Embedding dimension: {len(vec)}")   # expect 384 for bge-small
    print(f"First 8 numbers: {vec[:8]}")

    # Show that similar sentences embed closer than unrelated ones.
    import numpy as np
    a = embed_query("Where is FinSolve located?")
    b = embed_documents(["FinSolve is headquartered in Bangalore, India."])[0]
    c = embed_documents(["The marketing campaign ran in Q3 2024."])[0]
    # cosine similarity = dot product (vectors are already length-1)
    print(f"\nSimilarity to a RELATED sentence:   {np.dot(a, b):.3f}")
    print(f"Similarity to an UNRELATED sentence: {np.dot(a, c):.3f}")
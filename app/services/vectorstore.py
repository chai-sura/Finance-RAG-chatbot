"""
vectorstore.py — Phase 1, Step 3.

Job: store all chunk vectors (plus metadata) in Chroma, and provide a
search function. Chroma persists to disk so we embed ONCE, then query
many times. Metadata filtering here is what will power RBAC later.
"""
from typing import Optional, List
from pathlib import Path
import chromadb

from app.services.chunking import build_chunks
from app.services.embeddings import embed_documents, embed_query

# Where Chroma persists its data on disk. Built once, reused.
CHROMA_DIR = Path(__file__).resolve().parent.parent.parent / "chroma_store"
COLLECTION_NAME = "finsolve_docs"


def get_collection():
    """Open (or create) the persistent Chroma collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # A "collection" is like a table — a named bucket of vectors + metadata.
    return client.get_or_create_collection(name=COLLECTION_NAME)


def build_index():
    """One-time ingestion: chunk -> embed -> store all 286 chunks in Chroma."""
    chunks = build_chunks()
    print(f"Embedding {len(chunks)} chunks...")

    texts = [c["text"] for c in chunks]
    vectors = embed_documents(texts)   # documents: NO query prefix

    collection = get_collection()

    # Chroma stores four parallel lists, indexed together:
    #   ids       - a unique string id per chunk
    #   documents - the chunk text (returned with results, used in prompts)
    #   embeddings- the vectors (what similarity is computed on)
    #   metadatas - source/role/heading_path (used for citations + RBAC filter)
    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        documents=texts,
        embeddings=vectors,
        metadatas=[
            {
                "source": c["source"],
                "role": c["role"],
                "heading_path": c["heading_path"],
            }
            for c in chunks
        ],
    )
    print(f"Stored {collection.count()} chunks in Chroma at {CHROMA_DIR}")


def search(query: str, k: int = 8, allowed_roles: Optional[List[str]] = None):
    """Embed the query and return the k most similar chunks.

    If allowed_roles is given, only chunks whose role is in that list are
    considered — this is the RBAC filter, applied DURING the search.
    """
    collection = get_collection()
    query_vector = embed_query(query)   # query: WITH the BGE prefix

    # The metadata filter. Chroma's "$in" means "role must be one of these".
    where = {"role": {"$in": allowed_roles}} if allowed_roles else None

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=k,
        where=where,
    )
    return results


# Self-test: build the index, then run a couple of raw searches (no RBAC yet)
# so we can SEE retrieval working across the real corpus.
if __name__ == "__main__":
    build_index()

    print("\n--- Test search: 'Where is FinSolve headquartered?' ---")
    res = search("Where is FinSolve headquartered?", k=3)
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        print(f"\n[{meta['role']}] {meta['source']} > {meta['heading_path']}")
        print(f"  {doc[:200]}...")
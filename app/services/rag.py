"""
rag.py — the RAG orchestrator.

Ties retrieval + RBAC + generation into one answer-a-question flow, and
cites ONLY the sources the model actually used (not everything retrieved).
"""

import re
from app.services.reranker import rerank
from app.services.vectorstore import search
from app.services.llm import generate, rewrite_query
from app.utils.permissions import allowed_roles_for
from app.services.router import answer_with_sql

SYSTEM_PROMPT = (
    "You are FinSolve's internal assistant. Answer the user's question using "
    "ONLY the provided context. If the answer is not in the context, say "
    "'I don't have that information.' and nothing else. Do not make anything "
    "up. Be concise and factual. Answer directly in 1-3 sentences."
)


def build_prompt(question: str, chunks: list) -> str:
    """Assemble numbered, source-labeled context + the question.

    We ask the model to end with a 'USED SOURCES:' line listing the numbers
    it actually relied on, so we can cite precisely instead of over-citing.
    """
    context_blocks = []
    for i, (doc, meta) in enumerate(chunks, start=1):
        label = meta["source"]
        if meta.get("heading_path"):
            label += f" — {meta['heading_path']}"
        context_blocks.append(f"[Source {i}: {label}]\n{doc}")

    context = "\n\n".join(context_blocks)

    return (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer using only the context above. Write the answer in clean prose "
        f"WITHOUT mentioning source numbers in the answer text. Then, on a new "
        f"line, write 'USED SOURCES:' followed by the numbers of the sources you "
        f"actually used (e.g. 'USED SOURCES: 1, 3'). If the answer isn't in the "
        f"context, write 'USED SOURCES: none'."
    )


def _split_answer_and_sources(raw: str, chunks: list) -> tuple:
    """Separate the model's answer text from its 'USED SOURCES:' line, and
    map the cited numbers back to source labels."""
    # Find the 'USED SOURCES:' marker (case-insensitive).
    match = re.search(r"USED SOURCES:\s*(.*)$", raw, re.IGNORECASE | re.DOTALL)
    if not match:
        # Model didn't follow format — return the whole text, no sources.
        return raw.strip(), []
    
    used_part = match.group(1).strip()

    answer = raw[: match.start()].strip()
    # Remove any leftover inline "(Source N)" / "Source N" tags the model
    answer = re.sub(r"\s*\(?\bSources?\s*\d+(?:\s*,\s*\d+)*\)?", "", answer)
    answer = re.sub(r"\s{2,}", " ", answer).strip()  # tidy double spaces

    # Pull out the numbers the model listed (ignores 'none' gracefully).
    numbers = [int(n) for n in re.findall(r"\d+", used_part)]

    # Map each number back to its source label (numbers are 1-indexed).
    sources = []
    for n in numbers:
        if 1 <= n <= len(chunks):
            meta = chunks[n - 1][1]
            label = meta["source"]
            if meta.get("heading_path"):
                label += f" — {meta['heading_path']}"
            if label not in sources:
                sources.append(label)

    return answer, sources

def answer_question(question: str, role: str, history: list = None, k: int = 8) -> dict:
    history = history or []
    search_query = rewrite_query(history, question)
    allowed = allowed_roles_for(role)

    # --- SQL fork ---
    # Only users allowed to see HR data can have questions routed to the
    # employee table. This keeps RBAC intact across both paths.
    if "hr" in allowed:
        sql_result = answer_with_sql(search_query)
        if sql_result["ok"]:
            return {"answer": sql_result["answer"], "sources": sql_result["sources"]}
    # If not HR-authorized, or SQL didn't apply, fall through to RAG below.

    # --- RAG path ---
    # Cast a wider net for the reranker, then guard, then rerank down.
    results = search(search_query, k=20, allowed_roles=allowed)

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    # Defense-in-depth: drop anything outside the user's clearance BEFORE
    # reranking, so the reranker never even sees unauthorized chunks.
    allowed_candidates = [
        (doc, meta) for doc, meta in zip(docs, metas) if meta["role"] in allowed
    ]

    # Rerank the allowed candidates and keep the best 5.
    safe = rerank(search_query, allowed_candidates, top_n=5)

    if not safe:
        return {
            "answer": "I don't have information you have access to that answers this question.",
            "sources": [],
        }

    prompt = build_prompt(search_query, safe)
    raw = generate(prompt, system=SYSTEM_PROMPT)
    answer, sources = _split_answer_and_sources(raw, safe)

    return {"answer": answer, "sources": sources}

if __name__ == "__main__":
    q = "What were the key marketing campaigns and their performance?"
    for role in ["marketing", "finance", "employee"]:
        print(f"\n{'='*60}\nAsked as: {role.upper()}\n{'='*60}")
        result = answer_question(q, role)
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources: {result['sources']}")
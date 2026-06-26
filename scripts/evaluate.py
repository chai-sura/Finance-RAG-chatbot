"""
evaluate.py — RAG evaluation framework (run as a one-off script).

Stage 1: generate a test set of (question, reference_answer, role) from a
sample of the document chunks, using the LLM.

We build and inspect this before adding grading, so we can see the exam
questions first.
"""

import json
import random
from pathlib import Path
import csv
from app.services.rag import answer_question

from app.services.chunking import build_chunks
from app.services.llm import generate

random.seed(42)  # reproducible sample

# How many chunks to turn into test questions. Keep modest at first — each
# one is an LLM call, so 15-20 is plenty to start.
N_SAMPLES = 20


def generate_testset(per_role: int = 4) -> list:
    """Sample an EQUAL number of chunks per role, for a fair test set."""
    chunks = build_chunks()
    usable = [c for c in chunks if len(c["text"]) > 200]

    # Group by role, then sample the same count from each.
    by_role = {}
    for c in usable:
        by_role.setdefault(c["role"], []).append(c)

    sample = []
    for role, role_chunks in by_role.items():
        sample.extend(random.sample(role_chunks, min(per_role, len(role_chunks))))

    testset = []
    for i, chunk in enumerate(sample, start=1):
        prompt = (
            f"Based ONLY on the passage below, write one factual question a "
            f"user might ask, and the correct answer to it. The question must "
            f"be answerable from this passage alone.\n\n"
            f"Passage:\n{chunk['text']}\n\n"
            f"Respond in exactly this format:\n"
            f"QUESTION: <the question>\n"
            f"ANSWER: <the answer>"
        )
        raw = generate(prompt, system="You write factual QA pairs from passages.")
        question, answer = _parse_qa(raw)
        if question and answer:
            testset.append({
                "question": question,
                "reference_answer": answer,
                "role": chunk["role"],
                "source": chunk["source"],
            })
            print(f"[{i}/{len(sample)}] ({chunk['role']}) {question[:70]}")
    return testset


def _parse_qa(raw: str):
    """Pull QUESTION and ANSWER out of the LLM's response."""
    q, a = None, None
    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("QUESTION:"):
            q = line.split(":", 1)[1].strip()
        elif line.upper().startswith("ANSWER:"):
            a = line.split(":", 1)[1].strip()
    return q, a

def grade_answer(question: str, reference: str, system_answer: str) -> dict:
    """Ask the LLM to score the system's answer against the reference.

    Returns dict with faithfulness, relevance, conciseness (each 0.0-1.0).
    """
    prompt = (
        f"You are grading a chatbot's answer.\n\n"
        f"Question: {question}\n"
        f"Reference (correct) answer: {reference}\n"
        f"Chatbot's answer: {system_answer}\n\n"
        f"Score the chatbot's answer on three metrics from 0.0 to 1.0:\n"
        f"- faithfulness: does it match the reference / avoid making things up?\n"
        f"- relevance: does it actually address the question?\n"
        f"- conciseness: is it direct and free of padding?\n\n"
        f"Respond with ONLY a JSON object, e.g.:\n"
        f'{{"faithfulness": 0.9, "relevance": 1.0, "conciseness": 0.8}}'
    )
    raw = generate(prompt, system="You are a strict, fair grader. Respond only with JSON.")

    # Pull the JSON object out of the response.
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        scores = json.loads(raw[start:end])
        return {
            "faithfulness": float(scores.get("faithfulness", 0)),
            "relevance": float(scores.get("relevance", 0)),
            "conciseness": float(scores.get("conciseness", 0)),
        }
    except (ValueError, json.JSONDecodeError):
        # If grading fails to parse, return zeros so it's visible, not silent.
        return {"faithfulness": 0.0, "relevance": 0.0, "conciseness": 0.0}


def run_evaluation(testset: list) -> list:
    """Run each test question through the system and grade the answer."""
    results = []
    for i, item in enumerate(testset, start=1):
        # Run the ACTUAL system with the correct role.
        result = answer_question(item["question"], role=item["role"])
        system_answer = result["answer"]

        scores = grade_answer(
            item["question"], item["reference_answer"], system_answer
        )

        row = {
            "role": item["role"],
            "question": item["question"],
            "reference_answer": item["reference_answer"],
            "system_answer": system_answer,
            **scores,
        }
        results.append(row)
        print(f"[{i}/{len(testset)}] ({item['role']}) "
              f"F={scores['faithfulness']:.1f} "
              f"R={scores['relevance']:.1f} "
              f"C={scores['conciseness']:.1f}")
    return results

if __name__ == "__main__":
    import sys

    testset_path = Path(__file__).resolve().parent.parent / "eval_testset.json"

    # Reuse an existing test set if present, so the exam stays identical
    # across runs (fair before/after comparison). Pass "regen" to rebuild it.
    if testset_path.exists() and "regen" not in sys.argv:
        with open(testset_path) as f:
            testset = json.load(f)
        print(f"Loaded {len(testset)} existing QA pairs.\n")
    else:
        print("Generating test set...\n")
        testset = generate_testset()
        with open(testset_path, "w") as f:
            json.dump(testset, f, indent=2)

    print("Running evaluation...\n")
    results = run_evaluation(testset)

    # Aggregate.
    n = len(results)
    avg = {
        m: sum(r[m] for r in results) / n
        for m in ("faithfulness", "relevance", "conciseness")
    }
    overall = sum(avg.values()) / 3

    print("\n" + "=" * 40)
    print("BASELINE SCORES")
    print("=" * 40)
    print(f"Faithfulness: {avg['faithfulness']:.3f}")
    print(f"Relevance:    {avg['relevance']:.3f}")
    print(f"Conciseness:  {avg['conciseness']:.3f}")
    print(f"OVERALL:      {overall:.3f}")

    # Per-role breakdown — useful to spot the HR-lookup weakness.
    print("\nBy role (overall avg):")
    roles = sorted(set(r["role"] for r in results))
    for role in roles:
        rows = [r for r in results if r["role"] == role]
        ro = sum((r["faithfulness"] + r["relevance"] + r["conciseness"]) / 3
                 for r in rows) / len(rows)
        print(f"  {role:12} {ro:.3f}  ({len(rows)} questions)")

    # Save detailed results to CSV.
    csv_path = Path(__file__).resolve().parent.parent / "eval_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nDetailed results saved to {csv_path}")
"""
check_roles.py — thorough role-by-role behavior verification, with follow-ups.

For each role, runs a short *conversation* (so follow-ups carry history) and
prints what the assistant answered, with a rough PASS/FAIL where the expected
behavior is clear. Read the actual answers — the checks are a guide, not gospel.

Usage: python -m scripts.check_roles
"""

from app.services.rag import answer_question


def contains_any(text, words):
    t = text.lower()
    return any(w.lower() in t for w in words)


def is_denial(text):
    return contains_any(text, [
        "don't have", "do not have", "not provide", "no information",
        "not available", "cannot find", "couldn't find", "not provided",
        "not mentioned", "outside", "don't have access", "not have access",
    ])


def run_conversation(role, turns):
    """turns: list of (question, expectation_label, check_fn).
    Maintains history across turns so follow-ups are contextual."""
    print(f"\n{'='*60}\nROLE: {role.upper()}\n{'='*60}")
    history = []
    for question, label, check in turns:
        result = answer_question(question, role=role, history=history)
        answer = result["answer"]
        ok = check(answer) if check else None
        mark = " " if ok is None else ("PASS" if ok else "FAIL")
        print(f"\n[{mark}] {label}")
        print(f"   Q: {question}")
        print(f"   A: {answer[:160]}")
        if result.get("sources"):
            print(f"   src: {result['sources'][0]}")
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":

    run_conversation("hr", [
        ("How many employees are in the Sales department?", "SQL count", lambda a: contains_any(a, ["15"])),
        ("What about the Finance department?", "follow-up count (Finance)", lambda a: contains_any(a, ["employee", "finance"])),
        ("When did Aadhya Patel join?", "SQL lookup", lambda a: contains_any(a, ["2018", "november"])),
        ("What is the leave policy?", "general doc (allowed)", lambda a: not is_denial(a)),
        ("What were the marketing campaigns?", "DENY (no marketing access)", is_denial),
        ("What was the quarterly revenue?", "DENY (no finance access)", is_denial),
    ])

    run_conversation("finance", [
        ("What was the quarterly revenue?", "finance doc (allowed)", lambda a: not is_denial(a)),
        ("How was it split across quarters?", "follow-up (contextual)", lambda a: not is_denial(a)),
        ("What is the leave policy?", "general doc (allowed)", lambda a: not is_denial(a)),
        ("How many employees are in Sales?", "DENY (no HR table access)", is_denial),
        ("What were the marketing campaigns?", "DENY (no marketing access)", is_denial),
    ])

    run_conversation("marketing", [
        ("What were the key marketing campaigns?", "marketing doc (allowed)", lambda a: not is_denial(a)),
        ("Which one performed best?", "follow-up (contextual)", lambda a: not is_denial(a)),
        ("What is the leave policy?", "general doc (allowed)", lambda a: not is_denial(a)),
        ("What was the quarterly revenue?", "DENY (no finance access)", is_denial),
        ("What is Aadhya Patel's salary?", "DENY (no HR access)", is_denial),
    ])

    run_conversation("engineering", [
        ("What is the minimum unit test coverage?", "eng doc (allowed)", lambda a: not is_denial(a)),
        ("What databases are used?", "eng doc", lambda a: not is_denial(a)),
        ("What is the leave policy?", "general doc (allowed)", lambda a: not is_denial(a)),
        ("What were the marketing campaigns?", "DENY (no marketing access)", is_denial),
        ("How many employees are in Sales?", "DENY (no HR access)", is_denial),
    ])

    run_conversation("employee", [
        ("What is the leave policy?", "general doc (allowed)", lambda a: not is_denial(a)),
        ("How do I apply for it?", "follow-up (contextual)", lambda a: not is_denial(a)),
        ("What were the marketing campaigns?", "DENY (no marketing access)", is_denial),
        ("What was the quarterly revenue?", "DENY (no finance access)", is_denial),
        ("What is Aadhya Patel's salary?", "DENY (no HR access)", is_denial),
    ])

    run_conversation("c-level", [
        ("What were the key marketing campaigns?", "marketing (allowed)", lambda a: not is_denial(a)),
        ("What was the quarterly revenue?", "finance (allowed)", lambda a: not is_denial(a)),
        ("How many employees are in Sales?", "HR table (allowed)", lambda a: contains_any(a, ["15"])),
        ("What is the minimum unit test coverage?", "engineering (allowed)", lambda a: not is_denial(a)),
        ("What is the leave policy?", "general (allowed)", lambda a: not is_denial(a)),
    ])

    print(f"\n{'='*60}\nDone. Read the answers above — denials should deny, "
          f"allowed should answer.\n{'='*60}")
"""
router.py — handles the SQL path for structured (employee-table) questions.

SQL generation self-filters: the LLM either writes a SELECT for the employee
table, or replies NO_SQL when the table can't answer. The SQL path returns
ok=False (triggering RAG fallback) when the model refuses, the SQL fails, or
the query returns no rows.
"""

import re
from app.services.llm import generate
from app.services.sql_engine import get_schema, run_sql, TABLE_NAME


def _generate_sql(question: str) -> str:
    """Ask the LLM to write SQL for the question — or refuse with NO_SQL."""
    schema = get_schema()
    prompt = (
        f"You write DuckDB SQL queries against an employee records table.\n\n"
        f"{schema}\n\n"
        f"Question: \"{question}\"\n\n"
        f"If this question can be answered by querying the table above "
        f"(a specific employee's data, counts, averages, filters over the "
        f"records), write ONE SQL SELECT query and nothing else.\n\n"
        f"If the question is NOT answerable from these columns — for example "
        f"it asks about a policy, rule, procedure, or document — reply with "
        f"exactly: NO_SQL\n\n"
        f"Output only the SQL query, or only NO_SQL."
    )
    raw = generate(
        prompt,
        system="You either write a SQL SELECT, or reply NO_SQL. Nothing else.",
    ).strip()
    sql = re.sub(r"^```sql\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return sql


def _format_answer(question: str, columns: list, rows: list) -> str:
    """Turn raw query results into a natural-language answer."""
    result_text = f"Columns: {columns}\nRows:\n"
    for r in rows[:50]:
        result_text += f"  {r}\n"
    prompt = (
        f"Question: {question}\n\n"
        f"Database result:\n{result_text}\n\n"
        f"Answer the question in one or two clear sentences using this result. "
        f"Do not mention SQL or databases."
    )
    return generate(
        prompt, system="You answer questions from query results concisely."
    ).strip()


def answer_with_sql(question: str) -> dict:
    """Try the SQL path. Returns ok=False (caller falls back to RAG) if the
    question isn't a table question, SQL fails, or no rows come back."""
    try:
        sql = _generate_sql(question)
        if "NO_SQL" in sql.upper() or not sql.lower().startswith("select"):
            return {"answer": "", "sources": [], "ok": False}

        columns, rows = run_sql(sql)
        if not rows:
            return {"answer": "", "sources": [], "ok": False}

        answer = _format_answer(question, columns, rows)
        return {
            "answer": answer,
            "sources": [f"{TABLE_NAME} (employee records)"],
            "ok": True,
        }
    except Exception:
        return {"answer": "", "sources": [], "ok": False}
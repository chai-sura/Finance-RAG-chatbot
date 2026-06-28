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
        f"This table contains ONLY individual employee records (people, their "
        f"salary, department, join date, attendance, etc.).\n\n"
        f"Write ONE SQL SELECT query ONLY IF the question asks about employees "
        f"as people — a specific person, headcounts, salaries, attendance, or "
        f"statistics about staff.\n\n"
        f"Reply with exactly NO_SQL if the question is about anything else — "
        f"campaigns, reports, policies, processes, financial results, or any "
        f"business topic — EVEN IF it mentions a department name. For example:\n"
        f"- 'how many employees in Sales?' -> SQL (about staff)\n"
        f"- 'what were the marketing campaigns?' -> NO_SQL (about campaigns, "
        f"not employees)\n"
        f"- 'what is the finance report?' -> NO_SQL (about a report)\n\n"
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
        f"Answer in ONE short sentence using this result. Be direct — no filler "
        f"like 'based on the available data' or 'this represents'. "
        f"Do not mention SQL or databases."
    )
    return generate(
        prompt, system="You answer questions from query results concisely."
    ).strip()


def _answer_fits_question(question: str, answer: str) -> bool:
    """Check that the SQL-derived answer's CONTENT matches what was asked.

    Catches cases where the table produced a plausible but wrong-category
    answer (e.g. 'revenue' answered by summing employee salaries). On failure,
    the caller falls back to RAG — so a wrong rejection just retries via
    documents, never destroys a valid answer.
    """
    prompt = (
        f"A question was answered using an EMPLOYEE RECORDS database "
        f"(individual people: their salary, department, attendance, join date).\n\n"
        f"Question: \"{question}\"\n"
        f"Answer given: \"{answer}\"\n\n"
        f"Is this answer genuinely about EMPLOYEES/STAFF as people (headcount, "
        f"a person's record, staff statistics)? Company-level financials like "
        f"revenue, profit, or department budgets are NOT employee data, even if "
        f"a number was produced.\n\n"
        f"Reply YES if the answer is properly about employee/staff data. "
        f"Reply NO if it's really about company financials, reports, campaigns, "
        f"or any non-employee topic."
    )
    verdict = generate(
        prompt, system="You check if an answer is about employee data. Reply YES or NO."
    ).strip().upper()
    return verdict.startswith("YES")


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

        # Verify the answer is genuinely about employee data. If not (e.g. a
        # financial figure computed from salaries), fall back to RAG.
        if not _answer_fits_question(question, answer):
            return {"answer": "", "sources": [], "ok": False}

        return {
            "answer": answer,
            "sources": [f"{TABLE_NAME} (employee records)"],
            "ok": True,
        }
    except Exception:
        return {"answer": "", "sources": [], "ok": False}
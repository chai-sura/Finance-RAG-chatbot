"""
sql_engine.py — the structured-data (SQL) path.

Loads the HR CSV into an in-memory DuckDB table so we can answer precise
questions ("when did X join?", "who earns over 100k?", "avg attendance?")
with EXACT queries instead of fuzzy semantic search.

This file just makes the table queryable and runs SQL safely. The LLM
(text-to-SQL) is layered on top later.
"""

from pathlib import Path
import duckdb

# The HR CSV lives here. (Only this file is tabular; the rest are prose docs.)
CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "resources" / "data" / "hr" / "hr_data.csv"
)

TABLE_NAME = "employees"

# A single in-memory DuckDB connection, created once and reused.
_conn = None


def get_connection():
    """Open (once) an in-memory DuckDB and load the HR CSV into a table."""
    global _conn
    if _conn is None:
        _conn = duckdb.connect(database=":memory:")
        # read_csv_auto infers column names and types straight from the file.
        _conn.execute(
            f"CREATE TABLE {TABLE_NAME} AS "
            f"SELECT * FROM read_csv_auto('{CSV_PATH}')"
        )
    return _conn


def get_schema() -> str:
    """Return the table's columns and types as text, plus one sample row.

    This is handed to the LLM so it generates SQL with the REAL column
    names — the single most important thing for correct text-to-SQL.
    """
    conn = get_connection()

    # Column names and types.
    cols = conn.execute(f"DESCRIBE {TABLE_NAME}").fetchall()
    col_lines = "\n".join(f"  {name} ({dtype})" for name, dtype, *_ in cols)

    # One sample row so the LLM sees real value formats (e.g. how dates,
    # departments, names actually look).
    sample = conn.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 1").fetchall()

    return (
        f"Table: {TABLE_NAME}\n"
        f"Columns:\n{col_lines}\n\n"
        f"Sample row: {sample[0] if sample else 'none'}"
    )


def is_safe_select(sql: str) -> bool:
    """Allow ONLY read-only SELECT queries. Reject anything that could
    modify data (LLM-generated SQL must never DELETE/UPDATE/DROP)."""
    s = sql.strip().lower()
    # Must start with select...
    if not s.startswith("select"):
        return False
    # ...and must not contain any data-modifying keyword.
    forbidden = ("insert", "update", "delete", "drop", "alter",
                 "create", "replace", "attach", ";--", "pragma")
    return not any(word in s for word in forbidden)


def run_sql(sql: str):
    """Run a validated read-only query. Returns (columns, rows) or raises."""
    if not is_safe_select(sql):
        raise ValueError("Only read-only SELECT queries are allowed.")
    conn = get_connection()
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    return columns, rows


# Self-test: load the table and run a couple of hand-written queries, so we
# confirm the table is queryable BEFORE any LLM is involved.
if __name__ == "__main__":
    print("Schema:\n" + get_schema())

    print("\n--- Test 1: count employees ---")
    cols, rows = run_sql(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    print(f"{cols} -> {rows}")

    print("\n--- Test 2: a specific employee's join date ---")
    cols, rows = run_sql(
        f"SELECT full_name, date_of_joining FROM {TABLE_NAME} LIMIT 3"
    )
    print(cols)
    for r in rows:
        print(f"  {r}")

    print("\n--- Test 3: safety guard blocks a DELETE ---")
    try:
        run_sql("DELETE FROM employees")
        print("  PROBLEM: delete was not blocked!")
    except ValueError as e:
        print(f"  Correctly blocked: {e}")
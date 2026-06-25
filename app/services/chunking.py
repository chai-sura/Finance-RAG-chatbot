"""
chunk.py — Phase 1, Step 1 of the RAG pipeline.

Job: turn the files in resources/data/<role>/ into a list of well-tagged
text chunks. Each chunk carries metadata (source, role, heading_path) so
that later steps can (a) cite sources and (b) enforce role-based access.

This file does ONE thing: produce chunks. No embeddings, no vector store,
no LLM. We run it and inspect the output before building anything on top.
"""

import csv
from pathlib import Path

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# Where the documents live. Path(__file__) is this file; .parent.parent
# walks up from ingest/chunk.py to the project root, then into resources/data.
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "data"

# Which heading levels to split Markdown on, and what to name each level
# in the metadata. The splitter records, for each chunk, which h1/h2/h3 it
# sits under — that's our "heading_path" used for citations.
HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

# Cap on chunk size. Header sections can still be long; embeddings represent
# shorter, focused text better than huge blocks. ~1000 chars is a sane size;
# 100 chars of overlap means a thought spanning two chunks still partly
# appears in both, so retrieval doesn't lose it at the seam.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


def chunk_markdown(file_path: Path, role: str) -> list[dict]:
    """Split one Markdown file into chunks tagged with source/role/heading_path."""
    text = file_path.read_text(encoding="utf-8")

    # Pass 1: split on headers. strip_headers=False keeps the heading text
    # inside the chunk so the model sees it; metadata also records the path.
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    header_chunks = header_splitter.split_text(text)

    # Fallback: if a file had NO headers, header_chunks would be one giant
    # blob. Either way, Pass 2 below caps the size, so this stays robust.

    # Pass 2: cap oversized sections. This splitter breaks on paragraph,
    # then sentence, then word boundaries — never mid-word.
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    chunks = []
    for hc in header_chunks:
        # Build a readable breadcrumb from whatever heading levels exist,
        # e.g. "8. Monitoring > 8.2 Logging Framework > 8.2.1 Log Architecture"
        heading_path = " > ".join(
            hc.metadata[level] for level in ("h1", "h2", "h3") if level in hc.metadata
        )

        # Split this section down to size, then record each piece as a chunk.
        for piece in size_splitter.split_text(hc.page_content):
            chunks.append(
                {
                    "text": piece,
                    "source": file_path.name,   # for citations
                    "role": role,               # for RBAC filtering
                    "heading_path": heading_path,
                }
            )
    return chunks


def chunk_csv(file_path: Path, role: str) -> list[dict]:
    """Turn each CSV row into a readable, searchable text chunk.

    Raw comma-separated rows don't embed well — the model needs natural
    language. So we render each row as a sentence describing that employee.
    """
    chunks = []
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)  # each row becomes a dict keyed by column name
        for row in reader:
            # Render the row as prose. Note: the file's ACCESS role is `role`
            # (the folder = "hr"); the `department` column is descriptive text
            # about where the employee works — don't confuse the two.
            text = (
                f"Employee {row['full_name']} (ID {row['employee_id']}) is a "
                f"{row['role']} in the {row['department']} department, based in "
                f"{row['location']}. Email: {row['email']}. "
                f"Salary: {row['salary']}. Attendance: {row['attendance_pct']}%. "
                f"Performance rating: {row['performance_rating']}. "
                f"Leave balance: {row['leave_balance']}, leaves taken: {row['leaves_taken']}. "
                f"Joined on {row['date_of_joining']}; "
                f"last review on {row['last_review_date']}. "
                f"Manager ID: {row['manager_id']}."
            )
            chunks.append(
                {
                    "text": text,
                    "source": file_path.name,
                    "role": role,
                    "heading_path": "",  # not applicable to CSV rows
                }
            )
    return chunks


def build_chunks() -> list[dict]:
    """Walk resources/data/<role>/ and chunk every file by its type."""
    all_chunks = []

    # Each subfolder of DATA_DIR is a role (engineering, finance, hr, ...).
    for role_dir in sorted(DATA_DIR.iterdir()):
        if not role_dir.is_dir():
            continue
        role = role_dir.name  # folder name == access role. This is the RBAC hook.

        for file_path in sorted(role_dir.iterdir()):
            if file_path.suffix == ".md":
                all_chunks.extend(chunk_markdown(file_path, role))
            elif file_path.suffix == ".csv":
                all_chunks.extend(chunk_csv(file_path, role))
            # other file types ignored for now

    return all_chunks


# When run directly (python ingest/chunk.py), build the chunks and print a
# few samples so we can INSPECT before embedding anything.
if __name__ == "__main__":
    chunks = build_chunks()

    print(f"Total chunks produced: {len(chunks)}\n")

    # Count per role — a quick sanity check that every department got ingested.
    from collections import Counter
    by_role = Counter(c["role"] for c in chunks)
    print("Chunks per role:")
    for role, n in sorted(by_role.items()):
        print(f"  {role:12} {n}")
    print()

    # Show 2 sample chunks so you can see text + metadata together.
    print("--- Sample chunks ---")
    for c in chunks[:2]:
        print(f"\n[source] {c['source']}  [role] {c['role']}")
        print(f"[heading] {c['heading_path']}")
        print(f"[text] {c['text'][:300]}...")
# 🔐 VaultDesk — Role-Based RAG Assistant

VaultDesk is an internal AI assistant that answers questions from company documents while respecting **role-based access control (RBAC)**. Each user sees only what their clearance permits — a finance user can't retrieve HR salary data, an employee can't see marketing reports, and a C-level executive sees everything.

It combines **retrieval-augmented generation (RAG)** for documents with **structured-query routing** for tabular data, all behind a secure, role-aware access layer.

---

## Why it exists

Internal knowledge bases face a tension: make information easy to find, but don't leak sensitive data across departments. A naive chatbot with one shared knowledge base lets anyone surface anything. VaultDesk enforces access control **at retrieval time** — unauthorized data is never even fetched, so it can't reach the language model or the answer.

---

## The core insight

The company's knowledge isn't one kind of data — it's two:

- **Prose documents** (engineering, finance, marketing, general policies) — semantic search handles these well.
- **A structured employee table** (HR) — semantic search is *bad* at precise lookups over tabular data, because 100 near-identical rows look the same in vector space.

So VaultDesk routes each question to the right tool: structured questions (a person's salary, headcounts, averages) go to a **SQL engine** that queries the table exactly; everything else goes through the **RAG pipeline**.

---

## How it works

A signed-in user asks a question. The backend:

1. Verifies the user's **JWT** and reads their role.
2. **Rewrites** vague follow-ups into standalone questions using conversation history.
3. If the user is cleared for HR data, tries the **SQL path**: generate a query, run it on the employee table, return an exact answer. Falls back to RAG if the question isn't a table question or the query yields nothing.
4. Otherwise (or on fallback), runs **RAG**: embed the query, search the vector store *filtered to allowed roles*, rerank for precision, re-check access with a guard, and generate a grounded, cited answer.

```mermaid
flowchart TD
    A[User signs in] --> B[JWT issued, carries role]
    B --> C[Question + history]
    C --> D{HR-cleared and a table question?}
    D -- yes --> E[SQL: generate query, run on employee table]
    E --> F{Got a valid result?}
    F -- yes --> Z[Answer]
    F -- no --> G[RAG path]
    D -- no --> G[RAG path]
    G --> H[Embed query, search vector store filtered to role]
    H --> I[Rerank, guard, generate with citations]
    I --> Z[Answer]
```

---

## Key features

- **Role-based access control** — every document chunk is tagged by department. Retrieval is filtered to the user's allowed roles, then an independent guard re-checks each result before generation. Access is enforced across **both** the document and database paths.
- **Structured-query routing** — precise questions about employee data are answered with exact SQL queries (DuckDB), unlocking lookups *and* aggregations (counts, averages) that semantic search can't do.
- **Cross-encoder reranking** — retrieved candidates are re-scored for relevance to sharpen precision.
- **Grounded, cited answers** — responses come only from retrieved documents or query results, with sources. No hallucination.
- **Structure-aware chunking** — Markdown split by heading hierarchy (preserving the heading path for citations); CSV rows converted to natural-language chunks.
- **History-aware retrieval** — vague follow-ups are rewritten into standalone questions before retrieval.
- **Secure authentication** — JWT with bcrypt-hashed passwords; the role is carried in a signed token that can't be forged client-side.
- **Evaluation framework** — an automated pipeline generates a balanced test set from the documents and scores answers on faithfulness, relevance, and conciseness, enabling before/after measurement of changes.

---

## Results

The system was evaluated on a balanced test set (questions per department) scored on faithfulness, relevance, and conciseness:

| Change | Overall | HR score |
|--------|---------|----------|
| RAG baseline | 0.842 | 0.562 |
| + Reranker | 0.828 | 0.604 |
| + SQL routing | **0.862** | **0.733** |

The key finding: HR (tabular data) was the weak spot for pure semantic search, and **SQL routing lifted HR from 0.56 to 0.73** — a structural fix that retrieval tuning alone couldn't achieve.

---

## Roles and access

| Role | Can access |
|------|-----------|
| Finance | Financial reports, expenses, reimbursements + general info |
| Marketing | Campaign performance, customer feedback + general info |
| HR | Employee records, payroll, attendance + general info |
| Engineering | Architecture, processes, operational guidelines + general info |
| C-Level | All company data |
| Employee | General company info only (policies, events, FAQs) |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI |
| Frontend | Streamlit |
| Vector store | ChromaDB |
| Embeddings | BAAI/bge-small-en-v1.5 |
| Reranker | BAAI/bge-reranker-base |
| Structured queries | DuckDB |
| LLM | Groq · Llama 3.1 |
| Auth | JWT + bcrypt |

---

## Project structure

- **app/** — the application
  - **main.py** — FastAPI app: `/login`, `/chat` endpoints
  - **schemas/chat.py** — request/response models
  - **services/**
    - **chunking.py** — documents → tagged chunks
    - **embeddings.py** — BGE embedding wrapper
    - **vectorstore.py** — Chroma build + RBAC-filtered search
    - **reranker.py** — cross-encoder reranking
    - **sql_engine.py** — DuckDB engine + read-only query guard
    - **router.py** — text-to-SQL with RAG fallback
    - **rag.py** — orchestrates SQL fork + RAG path
    - **llm.py** — Groq calls + query rewriting
  - **utils/**
    - **auth.py** — JWT issue/verify, password hashing
    - **permissions.py** — role → allowed-roles map
- **frontend/app.py** — Streamlit UI
- **scripts/**
  - **hash_passwords.py** — one-time: hash demo passwords
  - **evaluate.py** — RAG evaluation framework
- **resources/data/** — company documents, by department
- **chroma_store/** — persisted vectors (generated, gitignored)
- **users.json** — demo users (gitignored)
- **.env** — secrets (gitignored)

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

Create a `.env` file:

```bash
GROQ_API_KEY=your_groq_key_here
JWT_SECRET=your_long_random_secret
```

Get a free Groq API key at https://console.groq.com. Generate a JWT secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

### 3. Set up demo users and build the index

```bash
python scripts/hash_passwords.py
python -m app.services.vectorstore
```

### 4. Run

Backend (terminal 1):

```bash
uvicorn app.main:app --reload
```

Frontend (terminal 2):

```bash
streamlit run frontend/app.py
```

### 5. (Optional) Run the evaluation

```bash
python -m scripts.evaluate
```

---

## Roadmap

- **Self-verification** — an answer-checking step to catch and re-route misclassified or unfaithful responses.
- **Table + text fusion retrieval** — answer mixed questions that span both the employee database and policy documents in a single response, fusing structured and unstructured sources.

---

## Notes

VaultDesk uses synthetic demo data for a fictional company (FinSolve Technologies). The vector store, `.env`, and `users.json` are gitignored and not included in the repository.

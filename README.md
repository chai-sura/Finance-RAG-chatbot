cat > README.md << 'ENDOFREADME'
# 🔐 VaultDesk — Role-Based RAG Assistant

VaultDesk is an internal AI assistant that answers questions from company documents while respecting **role-based access control (RBAC)**. Each user sees only what their clearance permits — a finance user can't retrieve HR salary data, an employee can't see marketing reports, and a C-level executive sees everything.

It pairs **retrieval-augmented generation (RAG)** with a secure, role-aware access layer, so answers are grounded in real company documents, cited to their source, and filtered by who's asking.

---

## Why it exists

Internal knowledge bases face a tension: make information easy to find, but don't leak sensitive data across departments. A naive chatbot with one shared knowledge base lets anyone surface anything. VaultDesk solves this by enforcing access control **at retrieval time** — unauthorized documents are never even fetched, so they can't reach the language model or the answer.

---

## How it works
User signs in ──> JWT issued (carries role)

│

▼

Question + history ──> /chat (JWT-protected)

│

├─ rewrite follow-ups into standalone questions (history-aware)

├─ resolve permissions for the user's role

├─ embed the query (BGE)

├─ search ChromaDB  ◄── filtered to allowed roles (RBAC)

├─ re-check each chunk's role (defense-in-depth guard)

├─ build a grounded prompt (context + citations)

└─ generate the answer (Groq / Llama 3.1)

│

▼

Answer + source citations

### Two phases

1. **Ingestion (run once):** company documents are chunked, tagged by department, embedded into vectors, and stored in ChromaDB.
2. **Serving:** users log in and ask questions; the system retrieves role-scoped chunks and generates cited answers.

---

## Key features

- **Role-based access control** — every document chunk is tagged by department. Retrieval is filtered to the user's allowed roles, then an **independent guard** re-checks each result before generation (defense in depth).
- **Grounded, cited answers** — responses come only from retrieved documents, each answer listing the sources it actually used. No hallucination.
- **Structure-aware chunking** — Markdown is split by heading hierarchy (preserving the heading path for precise citations); CSV rows are converted to natural-language chunks so tabular data is searchable.
- **History-aware retrieval** — vague follow-ups ("why", "what else?") are rewritten into standalone questions using conversation context before retrieval.
- **Secure authentication** — JWT with bcrypt-hashed passwords; the role is carried in a signed token that can't be forged client-side.
- **Clearance-themed UI** — a Streamlit interface that color-codes the session by the user's role, making access level visible at a glance.

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
| Embeddings | BAAI/bge-small-en-v1.5 (sentence-transformers) |
| LLM | Groq · Llama 3.1 8B |
| Auth | JWT + bcrypt |

---

## Architecture
┌─────────────┐      ┌──────────────────────────────────────┐

│  Streamlit  │      │            FastAPI backend           │

│  frontend   │      │                                      │

│             │      │  /login ──> verify + issue JWT       │

│  login ─────┼─────>│                                      │

│  chat  ─────┼─────>│  /chat  ──> JWT check                │

│             │      │             rewrite query (history)  │

│  bubbles <──┼──────┤             RBAC-filtered retrieval  │

│  + sources  │      │             guard ─> generate        │

└─────────────┘      └───────────────┬──────────────────────┘

│

┌───────────┴───────────┐

│       ChromaDB         │

│  (chunks + role tags)  │

└────────────────────────┘

---

## Project structure
.

├── app/

│   ├── main.py              # FastAPI app: /login, /chat endpoints

│   ├── schemas/

│   │   └── chat.py          # request/response models

│   ├── services/

│   │   ├── chunking.py      # documents -> tagged chunks

│   │   ├── embeddings.py    # BGE embedding wrapper

│   │   ├── vectorstore.py   # Chroma build + RBAC-filtered search

│   │   ├── rag.py           # retrieve + guard + generate

│   │   └── llm.py           # Groq calls + query rewriting

│   └── utils/

│       ├── auth.py          # JWT issue/verify, password hashing

│       └── permissions.py   # role -> allowed-roles map

├── frontend/

│   └── app.py               # Streamlit UI

├── scripts/

│   └── hash_passwords.py    # one-time: hash demo passwords

├── resources/data/          # company documents (by department)

│   ├── engineering/

│   ├── finance/

│   ├── general/

│   ├── hr/

│   └── marketing/

├── chroma_store/            # persisted vectors (generated, gitignored)

├── users.json               # demo users (gitignored)

├── .env                     # secrets (gitignored)

└── requirements.txt

---

## Setup

### 1. Install dependencies
python -m venv venv && source venv/bin/activate

pip install -r requirements.txt

### 2. Configure secrets

Create a `.env` file in the project root:
GROQ_API_KEY=your_groq_key_here

JWT_SECRET=your_long_random_secret

Get a free Groq API key at https://console.groq.com.
Generate a JWT secret with: `python -c "import secrets; print(secrets.token_hex(32))"`

### 3. Set up demo users

`users.json` holds demo accounts with bcrypt-hashed passwords (gitignored). If creating fresh, add usernames/roles, then run:
python scripts/hash_passwords.py

### 4. Build the vector index (one-time)
python -m app.services.vectorstore

### 5. Run

Backend (terminal 1):
uvicorn app.main:app --reload

Frontend (terminal 2):
streamlit run frontend/app.py

Open the Streamlit URL, sign in, and ask away.

---

## Demonstrating RBAC

Sign in as different roles and ask the **same question**:

- As a **Marketing** user: *"What were the key marketing campaigns?"* → a detailed, cited answer from the marketing reports.
- As an **HR** user: the same question → *"I don't have that information."* — the marketing documents are outside HR's clearance and are never retrieved.

The contrast shows access control working at the data level, not just in the UI.

---

## Design

The interface uses a **clearance-as-identity** concept: once signed in, the user's role color-codes the whole session (Executive gold, Finance teal, HR violet, Marketing coral, Engineering blue, Employee slate), so access level is visible at a glance. The layout is a branded top bar, Home/About tabs, and a chat that greets the user by name — answers render as cards with their sources listed beneath.

---

## Roadmap

- **Single Sign-On (SSO)** — integrate enterprise identity providers (OIDC) so access is managed centrally.
- **Human-in-the-loop** — when retrieved sources are relevant but conflict, surface them and let the user choose which to prioritize.
- **Reranking** — add a cross-encoder reranker to sharpen retrieval on ambiguous queries.

---

## Notes

VaultDesk uses synthetic demo data for a fictional company (FinSolve Technologies). The vector store, `.env`, and `users.json` are gitignored and not included in the repository.
ENDOFREADME
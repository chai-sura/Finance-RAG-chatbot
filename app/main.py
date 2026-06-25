"""
main.py — the FastAPI application.

Endpoints:
  POST /login  -> verify credentials, return a JWT
  POST /chat   -> (JWT-protected) answer a question for the user's role
  GET  /       -> simple health check

Auth is handled in app.utils.auth; RAG in app.services.rag. main.py just
wires them to HTTP endpoints.
"""

from fastapi import FastAPI, Depends

from app.schemas.chat import LoginRequest, ChatRequest, ChatResponse
from app.utils.auth import verify_user, create_token, get_current_user
from app.services.rag import answer_question

app = FastAPI(title="VaultDesk")


@app.get("/")
def health():
    """Simple check that the server is up."""
    return {"status": "ok"}


@app.post("/login")
def login(req: LoginRequest):
    """Verify username/password, return a signed JWT carrying the role."""
    # verify_user checks the password against the stored bcrypt hash and
    # raises 401 if it's wrong.
    user = verify_user(req.username, req.password)
    token = create_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    result = answer_question(req.message, role=user["role"], history=history)
    return ChatResponse(answer=result["answer"], sources=result["sources"])
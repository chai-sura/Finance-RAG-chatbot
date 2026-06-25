"""Request/response shapes for the API."""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
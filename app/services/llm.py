"""
llm.py — the generation layer's connection to Groq.

Single responsibility: take a prompt (and optional system instruction),
send it to Groq's LLM, return the generated text. Nothing about RAG or
roles lives here — that keeps the LLM provider swappable in one place.
"""

import os
from groq import Groq
from dotenv import load_dotenv

# Load variables from the .env file into the environment so os.getenv can read.
load_dotenv()

# The model we chose: Llama 3.1 8B, served by Groq (very fast inference).
MODEL = "llama-3.1-8b-instant"

# Create the Groq client once. It reads the API key from the environment.
# If the key is missing, we fail early with a clear message rather than a
# confusing error deep inside an API call later.
_api_key = os.getenv("GROQ_API_KEY")
if not _api_key:
    raise RuntimeError(
        "GROQ_API_KEY not found. Add it to your .env file as GROQ_API_KEY=..."
    )

_client = Groq(api_key=_api_key)


def generate(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Send a prompt to Groq and return the model's text response.

    Args:
        prompt: the user-facing content (in our case, context + question).
        system: a high-level instruction that sets the model's behavior.

    Returns:
        The generated text as a plain string.
    """
    # Chat models take a list of "messages", each with a role:
    #   - "system": sets overall behavior/rules (highest-level steering)
    #   - "user":   the actual request/content
    # (there's also "assistant" for prior replies, used in multi-turn chat)
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,   # low = focused/factual; high = creative/random.
                           # For RAG we want faithful answers, so keep it low.
    )

    # The API returns a structured object. The generated text lives at
    # choices[0].message.content. We pull just that string out.
    return response.choices[0].message.content

def rewrite_query(history: list, new_message: str) -> str:
    """Rewrite a possibly-vague follow-up into a standalone question.
    history: list of {"role": "user"/"assistant", "content": str}
    Returns a self-contained question suitable for retrieval.

    Only rewrites when the new message actually depends on prior context.
    Self-contained questions pass through UNCHANGED, so unrelated history
    can't poison them (e.g. "what is the leave policy?" after SQL questions).
    """
    if not history:
        return new_message

    msg = new_message.strip()
    words = msg.split()

    # A message that's short OR contains a reference/follow-up cue likely
    # depends on prior context. Everything else is treated as self-contained.
    is_short = len(words) <= 3
    has_followup_cue = any(
        cue in msg.lower()
        for cue in (" it", " it?", " that", " those", " this", " one",
                    "them", "what about", "how about", "why", "and ", "ones")
    )

    # Self-contained question -> use as-is, do NOT rewrite.
    if not is_short and not has_followup_cue:
        return new_message

    # Looks like a follow-up -> rewrite using recent context.
    transcript = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in history[-6:]
    )
    prompt = (
        f"Given this conversation:\n{transcript}\n\n"
        f"The user now says: \"{new_message}\"\n\n"
        f"Rewrite the user's latest message as a single, standalone question "
        f"that includes all needed context from the conversation. If it's "
        f"already standalone, return it unchanged. Respond with ONLY the "
        f"rewritten question, nothing else."
    )
    rewritten = generate(
        prompt,
        system="You rewrite follow-up messages into standalone questions.",
    ).strip()
    return rewritten if rewritten else new_message

# Self-test: run `python -m app.services.llm` to confirm the key works and
# we can reach Groq, BEFORE wiring it into the RAG flow.
if __name__ == "__main__":
    answer = generate("Say hello and confirm you are working in one sentence.")
    print("Groq response:")
    print(answer)
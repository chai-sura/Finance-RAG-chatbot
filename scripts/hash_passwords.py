"""One-time utility: rewrite users.json with bcrypt-hashed passwords."""
import json
from pathlib import Path
from passlib.context import CryptContext

ROOT = Path(__file__).resolve().parent.parent
USERS_PATH = ROOT / "users.json"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

with open(USERS_PATH) as f:
    users = json.load(f)

for username, info in users.items():
    if not info["password"].startswith("$2"):       # skip if already hashed
        info["password"] = pwd_context.hash(info["password"])
        print(f"Hashed password for {username}")
    else:
        print(f"{username} already hashed, skipping")

with open(USERS_PATH, "w") as f:
    json.dump(users, f, indent=2)
print(f"\nDone. {USERS_PATH} now stores bcrypt hashes.")
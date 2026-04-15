---
name: backend-guide
description: Backend coding guide for the Steinbot FastAPI server. Reference for auth patterns, session handling, and API conventions used in this project.
---

You are helping with the Steinbot backend, a FastAPI server written in Python.
Use the guides below as reference when writing or reviewing backend code.

---

# Login / Authentication Guide

Steinbot currently uses **stateless session tokens** (UUIDs) — not user accounts or passwords.
If full user authentication is ever added, follow these conventions:

## Session Flow (current)
1. Client calls `POST /session` → server generates a UUID, stores it in the in-memory `sessions` dict, returns it
2. Client sends `session_id` on every subsequent request
3. Server validates the session exists before processing

```python
# Creating a session
session_id = str(uuid.uuid4())
sessions[session_id] = {"current_book_id": None, "history": []}

# Validating a session
session = sessions.get(req.session_id)
if not session:
    raise HTTPException(status_code=404, detail="Session not found")
```

## If Adding Real User Auth (future)

Prefer **JWT tokens** over server-side session storage — they're stateless and scale better.

**Recommended library:** `python-jose` for JWT, `passlib` for password hashing

```python
from passlib.context import CryptContext
from jose import JWTError, jwt

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str, secret: str, expire_minutes: int = 60) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")
```

**FastAPI dependency injection pattern for protected routes:**

```python
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/protected")
def protected_route(user_id: str = Depends(get_current_user)):
    ...
```

## Security Rules
- Never store plain-text passwords — always bcrypt
- Keep `SECRET_KEY` in `.env`, never in source code
- Set short expiry on access tokens (15–60 min); use refresh tokens for longer sessions
- HTTPS only in production — tokens in headers can be intercepted over plain HTTP

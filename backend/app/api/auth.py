from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import bcrypt
import secrets
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

GUEST_USERNAME = "guest"

def create_users_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                hashed_password TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

        # Google sign-in support — added alongside the original password-only schema
        for col, col_type in [("google_id", "VARCHAR(255)"), ("email", "VARCHAR(255)")]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()
        try:
            conn.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS users_google_id_idx ON users (google_id)"))
            conn.commit()
        except Exception:
            conn.rollback()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False  # Google-only accounts have no password to check against
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": username, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

def get_user(username: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, hashed_password FROM users WHERE username = :u"),
            {"u": username}
        ).fetchone()
    return {"username": row[0], "hashed_password": row[1]} if row else None

def get_or_create_google_user(google_id: str, email: str | None, email_verified: bool) -> str:
    """Find the username for this Google account, linking to an existing
    password account with a matching verified email, or creating a fresh one."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username FROM users WHERE google_id = :gid"), {"gid": google_id}
        ).fetchone()
        if row:
            return row[0]

        # Only auto-link to an existing username/password account if Google
        # has actually verified the email — otherwise this would let anyone
        # claim an account just by typing someone else's email into Google.
        if email and email_verified:
            row = conn.execute(
                text("SELECT username FROM users WHERE email = :email"), {"email": email}
            ).fetchone()
            if row:
                username = row[0]
                conn.execute(
                    text("UPDATE users SET google_id = :gid WHERE username = :u"),
                    {"gid": google_id, "u": username}
                )
                conn.commit()
                return username

        base_username = (email.split("@")[0] if email else f"google_{google_id[:8]}")[:45]
        username = base_username
        suffix = 1
        while conn.execute(text("SELECT 1 FROM users WHERE username = :u"), {"u": username}).fetchone():
            username = f"{base_username}{suffix}"
            suffix += 1

        conn.execute(
            text("INSERT INTO users (username, hashed_password, google_id, email) VALUES (:u, NULL, :gid, :email)"),
            {"u": username, "gid": google_id, "email": email}
        )
        conn.commit()
        return username

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})

def get_current_user_id(username: str = Depends(get_current_user)) -> int:
    """Numeric user id for the logged-in user, used to scope ownership of rules/watchlist items."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return row[0]

def get_user_email(user_id: int) -> str | None:
    """Email for a given user id, or None if they have none on file (e.g. older
    password-only accounts registered before email was required)."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT email FROM users WHERE id = :id"), {"id": user_id}).fetchone()
    return row[0] if row else None

def get_username_by_id(user_id: int) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT username FROM users WHERE id = :id"), {"id": user_id}).fetchone()
    return row[0] if row else None

def get_alpaca_credentials(username: str | None) -> tuple[str, str]:
    """Alpaca key/secret to trade with for a given username. The guest account
    trades against its own isolated paper account (when configured) so a demo
    visitor can never see or touch the primary account's real paper positions,
    orders, or balance."""
    if username == GUEST_USERNAME and settings.alpaca_guest_api_key:
        return settings.alpaca_guest_api_key, settings.alpaca_guest_secret_key
    return settings.alpaca_api_key, settings.alpaca_secret_key

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class GoogleAuthRequest(BaseModel):
    credential: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str

@router.post("/auth/register", response_model=LoginResponse)
def register(req: RegisterRequest):
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if req.email and ("@" not in req.email or "." not in req.email.split("@")[-1]):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if get_user(req.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    hashed = hash_password(req.password)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, hashed_password, email) VALUES (:u, :h, :e)"),
            {"u": req.username, "h": hashed, "e": req.email}
        )
        conn.commit()
    token = create_token(req.username)
    print(f"✅ Registered: {req.username}", flush=True)
    return LoginResponse(access_token=token, token_type="bearer", username=req.username)

@router.post("/auth/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(form.username)
    print(f"✅ Login: {form.username}", flush=True)
    return LoginResponse(access_token=token, token_type="bearer", username=form.username)

@router.post("/auth/guest", response_model=LoginResponse)
def guest_login():
    """Logs into a single shared, auto-provisioned 'guest' account, so a demo
    visitor (e.g. from a resume link) can explore full functionality without
    registering. The account gets a random, never-shared password, so it can
    only ever be reached through this endpoint, never the normal login form."""
    if not get_user(GUEST_USERNAME):
        hashed = hash_password(secrets.token_urlsafe(32))
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO users (username, hashed_password) VALUES (:u, :h)"),
                {"u": GUEST_USERNAME, "h": hashed}
            )
            conn.commit()
    token = create_token(GUEST_USERNAME)
    print("✅ Guest login", flush=True)
    return LoginResponse(access_token=token, token_type="bearer", username=GUEST_USERNAME)

@router.post("/auth/google", response_model=LoginResponse)
def google_login(req: GoogleAuthRequest):
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google sign-in is not configured on this server")
    try:
        idinfo = google_id_token.verify_oauth2_token(
            req.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    google_id = idinfo["sub"]
    email = idinfo.get("email")
    email_verified = bool(idinfo.get("email_verified", False))

    username = get_or_create_google_user(google_id, email, email_verified)
    token = create_token(username)
    print(f"✅ Google sign-in: {username}", flush=True)
    return LoginResponse(access_token=token, token_type="bearer", username=username)

@router.get("/auth/me")
def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user, "authenticated": True}

@router.post("/auth/logout")
def logout(current_user: str = Depends(get_current_user)):
    print(f"👋 Logout: {current_user}", flush=True)
    return {"message": "Logged out successfully"}

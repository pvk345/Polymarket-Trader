from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_users_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
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

class RegisterRequest(BaseModel):
    username: str
    password: str

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
    if get_user(req.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    hashed = hash_password(req.password)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, hashed_password) VALUES (:u, :h)"),
            {"u": req.username, "h": hashed}
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

@router.get("/auth/me")
def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user, "authenticated": True}

@router.post("/auth/logout")
def logout(current_user: str = Depends(get_current_user)):
    print(f"👋 Logout: {current_user}", flush=True)
    return {"message": "Logged out successfully"}

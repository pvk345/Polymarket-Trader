import pytest
from datetime import datetime, timedelta
from jose import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.api.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
)


class TestPasswordHashing:
    def test_correct_password_verifies(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_not_the_plaintext(self):
        hashed = hash_password("hunter2")
        assert hashed != "hunter2"

    def test_none_hash_fails_closed(self):
        # Google-only accounts store no password hash — must never verify as True
        assert verify_password("anything", None) is False

    def test_same_password_hashes_differently_each_time(self):
        # bcrypt salts each hash — this guards against someone swapping in a
        # non-salted hash function later without noticing
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True


class TestJWT:
    def test_create_token_round_trips(self):
        token = create_token("alice")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "alice"

    def test_token_has_future_expiry(self):
        token = create_token("alice")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["exp"] > datetime.utcnow().timestamp()

    def test_get_current_user_accepts_valid_token(self):
        token = create_token("bob")
        assert get_current_user(token) == "bob"

    def test_get_current_user_rejects_garbage_token(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("not-a-real-jwt")
        assert exc_info.value.status_code == 401

    def test_get_current_user_rejects_expired_token(self):
        expired = jwt.encode(
            {"sub": "carol", "exp": datetime.utcnow() - timedelta(minutes=1)},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(expired)
        assert exc_info.value.status_code == 401

    def test_get_current_user_rejects_token_signed_with_wrong_secret(self):
        forged = jwt.encode(
            {"sub": "mallory", "exp": datetime.utcnow() + timedelta(minutes=5)},
            "a-different-secret",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(forged)
        assert exc_info.value.status_code == 401

    def test_get_current_user_rejects_token_missing_subject(self):
        no_sub = jwt.encode(
            {"exp": datetime.utcnow() + timedelta(minutes=5)},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(no_sub)
        assert exc_info.value.status_code == 401

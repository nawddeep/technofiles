"""
JWT-Based Authentication System (Requirement 1)
Secure Password Storage with Argon2id (Requirement 15)
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, jsonify

from database import get_db


def get_jwt_secret():
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise ValueError("JWT_SECRET_KEY environment variable is not set")
    if len(secret) < 32:
        raise ValueError("JWT_SECRET_KEY must be at least 32 characters (256 bits)")
    return secret


def generate_access_token(user_id, email):
    payload = {
        "user_id": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def generate_refresh_token(user_id, device_info="", ip_address=""):
    jti = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    conn = get_db()
    conn.execute(
        "INSERT INTO refresh_tokens (user_id, token_jti, expires_at, device_info, ip_address) VALUES (?, ?, ?, ?, ?)",
        (user_id, jti, expires_at.isoformat(), device_info, ip_address)
    )
    conn.commit()
    conn.close()
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def refresh_access_token(refresh_token_str):
    payload = decode_token(refresh_token_str)
    if not payload:
        return None, "Invalid or expired refresh token"
    if payload.get("type") != "refresh":
        return None, "Invalid token type"
    jti = payload.get("jti")
    user_id = payload.get("user_id")
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, is_revoked, expires_at FROM refresh_tokens WHERE token_jti = ?",
        (jti,)
    ).fetchone()
    if not row:
        conn.close()
        return None, "Refresh token not found"
    if row["is_revoked"]:
        conn.close()
        return None, "Refresh token has been revoked"
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        conn.execute("DELETE FROM refresh_tokens WHERE token_jti = ?", (jti,))
        conn.commit()
        conn.close()
        return None, "Refresh token has expired"
    user_row = conn.execute(
        "SELECT id, full_name, email, is_onboarded, is_verified, onboarding_data FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not user_row:
        return None, "User not found"
    new_access_token = generate_access_token(user_id, user_row["email"])
    user_data = {
        "id": user_row["id"],
        "full_name": user_row["full_name"],
        "email": user_row["email"],
        "is_onboarded": bool(user_row["is_onboarded"]),
        "is_verified": bool(user_row["is_verified"]),
        "onboarding_data": user_row["onboarding_data"] or ""
    }
    return new_access_token, user_data


def revoke_refresh_token(jti):
    conn = get_db()
    conn.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE token_jti = ?", (jti,))
    conn.commit()
    conn.close()


def revoke_all_refresh_tokens(user_id):
    conn = get_db()
    conn.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def hash_password(password):
    try:
        from argon2 import PasswordHasher, Type
        ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)
        return ph.hash(password)
    except ImportError:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(hashed_password, plain_password):
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError, InvalidHashError
        ph = PasswordHasher()
        try:
            ph.verify(hashed_password, plain_password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False
    except ImportError:
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, plain_password)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required."}), 401
        token = auth_header[7:]
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token."}), 401
        if payload.get("type") != "access":
            return jsonify({"error": "Invalid token type."}), 401
        user_id = payload.get("user_id")
        conn = get_db()
        row = conn.execute(
            "SELECT id, full_name, email, is_onboarded, is_verified, onboarding_data, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "User not found."}), 401
        user = {
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "is_onboarded": bool(row["is_onboarded"]),
            "is_verified": bool(row["is_verified"]),
            "onboarding_data": row["onboarding_data"] or "",
            "member_since": row["created_at"][:10] if row["created_at"] else "—"
        }
        return f(user, *args, **kwargs)
    return decorated


def require_verified_email(f):
    @wraps(f)
    def decorated(user, *args, **kwargs):
        if not user.get("is_verified"):
            return jsonify({"error": "Email verification required.", "code": "EMAIL_NOT_VERIFIED"}), 403
        return f(user, *args, **kwargs)
    return decorated


def get_current_user_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def get_current_user_agent():
    return request.headers.get("User-Agent", "Unknown")
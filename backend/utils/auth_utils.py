import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone
import jwt as pyjwt
import psycopg2
from database import get_db

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

try:
    from argon2 import PasswordHasher, Type
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
except ImportError:
    pass

def hash_password(password):
    ph = PasswordHasher(
        time_cost=3, memory_cost=65536, parallelism=4,
        hash_len=32, salt_len=16, type=Type.ID
    )
    return ph.hash(password)

def verify_password(hashed, plain):
    ph = PasswordHasher()
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False

def generate_access_token(user_id, email):
    payload = {
        "user_id": user_id, 
        "email": email, 
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)
    }
    return pyjwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

def generate_refresh_token(user_id, device_info="", ip_address=""):
    jti = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO refresh_tokens (user_id, token_jti, expires_at, device_info, ip_address) VALUES (%s, %s, %s, %s, %s)",
            (user_id, jti, expires_at.isoformat(), device_info, ip_address)
        )
        conn.commit()
    finally:
        conn.close()
        
    payload = {
        "user_id": user_id, "type": "refresh", "jti": jti,
        "exp": expires_at, "iat": datetime.now(timezone.utc)
    }
    return pyjwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        return pyjwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None

def refresh_access_token(refresh_token_str):
    payload = decode_token(refresh_token_str)
    if not payload or payload.get("type") != "refresh":
        return None, "Invalid or expired refresh token"
    
    jti = payload.get("jti")
    user_id = payload.get("user_id")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, is_revoked, expires_at FROM refresh_tokens WHERE token_jti = %s",
        (jti,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None, "Refresh token not found"
        
    if row["is_revoked"]:
        conn.close()
        return None, "Refresh token has been revoked"
        
    if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
        cursor.execute("DELETE FROM refresh_tokens WHERE token_jti = %s", (jti,))
        conn.commit()
        conn.close()
        return None, "Refresh token has expired"
        
    cursor.execute(
        "SELECT id, full_name, email, is_onboarded, is_verified, onboarding_data FROM users WHERE id = %s",
        (user_id,)
    )
    user_row = cursor.fetchone()
    conn.close()
    
    if not user_row:
        return None, "User not found"
        
    new_token = generate_access_token(user_id, user_row["email"])
    user_data = {
        "id": user_row["id"], "full_name": user_row["full_name"],
        "email": user_row["email"], "is_onboarded": bool(user_row["is_onboarded"]),
        "is_verified": bool(user_row["is_verified"]),
        "onboarding_data": user_row["onboarding_data"] or ""
    }
    return new_token, user_data

def revoke_all_refresh_tokens(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()

def create_session(user_id, user_agent="", ip_address=""):
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at, user_agent, ip_address) VALUES (%s, %s, %s, %s, %s)",
            (session_id, user_id, expires_at.isoformat(), user_agent, ip_address)
        )
        conn.commit()
    finally:
        conn.close()
    return session_id

def invalidate_all_sessions(user_id, except_session_id=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        if except_session_id:
            cursor.execute(
                "UPDATE sessions SET is_active = FALSE WHERE user_id = %s AND session_id != %s",
                (user_id, except_session_id)
            )
        else:
            cursor.execute("UPDATE sessions SET is_active = FALSE WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()

def generate_email_verification_token(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (user_id, token, expires_at.isoformat())
        )
        conn.commit()
    finally:
        conn.close()
    return token

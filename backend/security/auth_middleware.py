import logging
from datetime import datetime, timezone
from functools import wraps
from flask import request, jsonify
from database import get_db
import jwt as pyjwt
import os

logger = logging.getLogger("SAAITA")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

def decode_token(token):
    try:
        return pyjwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check httpOnly cookie first (browser clients), then Authorization header (API clients)
        token = request.cookies.get("access_token") or ""
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            return jsonify({"error": "Authentication required."}), 401
            
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return jsonify({"error": "Invalid or expired token."}), 401
            
        user_id = payload.get("user_id")
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, full_name, email, is_onboarded, is_verified, onboarding_data, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
        finally:
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
            "member_since": row["created_at"].isoformat() if row["created_at"] else ""
        }
        return f(user, *args, **kwargs)
    return decorated

def require_verified_email(f):
    """Enforce email verification, with a 7-day grace period for new accounts."""
    @wraps(f)
    def decorated(user, *args, **kwargs):
        if not user.get("is_verified"):
            try:
                created_at = datetime.fromisoformat(user.get("member_since", ""))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - created_at).days >= 7:
                    return jsonify({
                        "error": "Email verification required to continue using SAAITA.",
                        "code": "EMAIL_NOT_VERIFIED"
                    }), 403
            except (ValueError, TypeError):
                # If we can't parse the date, enforce verification to be safe
                return jsonify({
                    "error": "Email verification required.",
                    "code": "EMAIL_NOT_VERIFIED"
                }), 403
        return f(user, *args, **kwargs)
    return decorated

def get_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"

def get_ua():
    return request.headers.get("User-Agent", "Unknown")

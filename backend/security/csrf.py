import secrets
import os
import time
from functools import wraps
from flask import request, jsonify
from extensions import REDIS_AVAILABLE, redis_client, redis_fallback

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",")] if os.getenv("ALLOWED_ORIGINS") else []

def generate_csrf_token(session_id=""):
    token = secrets.token_urlsafe(32)
    if REDIS_AVAILABLE and redis_client:
        redis_client.setex(f"csrf:{token}", 3600, session_id)
    else:
        redis_fallback[f"csrf:{token}"] = (session_id, time.time() + 3600)
    return token

def validate_csrf_token(token):
    if REDIS_AVAILABLE and redis_client:
        return redis_client.exists(f"csrf:{token}") > 0
    else:
        if token in redis_fallback:
            _, expiry = redis_fallback[token]
            if time.time() < expiry:
                return True
            else:
                del redis_fallback[token]
        return False

def validate_origin():
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    if not origin and not referer:
        return True
    if origin:
        return origin in ALLOWED_ORIGINS
    return any(referer.startswith(allowed) for allowed in ALLOWED_ORIGINS)

def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return f(*args, **kwargs)
        if not validate_origin():
            return jsonify({"error": "Invalid origin."}), 403
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not csrf_token:
            return jsonify({"error": "CSRF token missing."}), 403
        if not validate_csrf_token(csrf_token):
            return jsonify({"error": "Invalid CSRF token."}), 403
        return f(*args, **kwargs)
    return decorated
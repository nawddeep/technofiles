"""
CSRF Protection System (Requirement 2)
"""
import secrets
import os
from functools import wraps
from flask import request, jsonify

_csrf_tokens = {}

def generate_csrf_token(session_id=""):
    token = secrets.token_urlsafe(32)
    _csrf_tokens[token] = session_id
    return token

def validate_csrf_token(token):
    return token in _csrf_tokens

def rotate_csrf_token(old_token, session_id=""):
    if old_token in _csrf_tokens:
        del _csrf_tokens[old_token]
    return generate_csrf_token(session_id)

def cleanup_csrf_tokens():
    if len(_csrf_tokens) > 10000:
        keys_to_remove = list(_csrf_tokens.keys())[:5000]
        for key in keys_to_remove:
            del _csrf_tokens[key]

def validate_origin():
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    if not origin and not referer:
        return True
    allowed_origins = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]
    env_origins = os.environ.get("ALLOWED_ORIGINS", "")
    if env_origins:
        allowed_origins = env_origins.split(",")
    if origin:
        return origin in allowed_origins
    if referer:
        for allowed in allowed_origins:
            if referer.startswith(allowed):
                return True
        return False
    return True

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

def set_csrf_cookie(response, token):
    response.set_cookie("csrf_token", token, samesite="Lax", httponly=False, secure=request.is_secure, path="/")
    return response
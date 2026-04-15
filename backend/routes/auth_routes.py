import os
import json
import time
import psycopg2
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from database import get_db
from extensions import limiter, redis_client, REDIS_AVAILABLE
from utils.validation import has_null_bytes, validate_schema, validate_email, validate_password, MAX_JSON
from utils.auth_utils import (
    hash_password, verify_password, generate_access_token, generate_refresh_token,
    create_session, invalidate_all_sessions, generate_email_verification_token,
    refresh_access_token, revoke_all_refresh_tokens
)
from utils.audit_utils import audit_log, record_login_attempt, check_brute_force
from security.auth_middleware import require_auth, get_ip, get_ua
from security.csrf import generate_csrf_token, csrf_protect
from services.queue_service import send_email

auth_bp = Blueprint("auth", __name__)
APP_URL = os.getenv("APP_URL", "http://localhost:5173")
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

# Environment-based rate limits — strict in prod, relaxed for local dev
SIGNUP_LIMIT = "3 per hour" if IS_PRODUCTION else "50 per hour"
LOGIN_LIMIT = "5 per 15 minutes" if IS_PRODUCTION else "30 per 15 minutes"
REFRESH_LIMIT = "10 per hour" if IS_PRODUCTION else "60 per hour"

# Dummy hash for constant-time comparison when user does not exist (timing attack mitigation)
# Pre-baked invalid hash so Argon2 still runs and constant time is preserved
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dummysaltdummysaltdummy$dummyhash0000000000000000000000000000000000000"


def set_auth_cookies(response, access_token, refresh_token, csrf_token):
    secure = request.is_secure
    # Always use Strict to prevent CSRF on GET requests — SameSite=Lax is insufficient
    response.set_cookie("access_token", access_token, httponly=True, secure=secure, samesite="Strict", path="/", max_age=900)
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=secure, samesite="Strict", path="/api/auth/refresh", max_age=604800)
    response.set_cookie("csrf_token", csrf_token, httponly=False, secure=secure, samesite="Strict", path="/")
    return response

@auth_bp.route("/csrf-token", methods=["GET"])
def get_csrf_token_route():
    token = generate_csrf_token()
    resp = jsonify({"csrf_token": token})
    resp.set_cookie("csrf_token", token, samesite="Lax", httponly=False, secure=request.is_secure, path="/")
    return resp

@auth_bp.route("/signup", methods=["POST"])
@limiter.limit(SIGNUP_LIMIT)
def signup():
    ip_address = get_ip()
    user_agent = get_ua()
    if request.content_length and request.content_length > MAX_JSON:
        return jsonify({"error": "Request payload too large."}), 413
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
    ok, msg = validate_schema(data, "signup")
    if not ok:
        return jsonify({"error": msg}), 400
        
    full_name = data.get("fullName", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    
    ok, msg = validate_email(email)
    if not ok: return jsonify({"error": msg}), 400
    ok, msg = validate_password(password)
    if not ok: return jsonify({"error": msg}), 400
    
    pwd_hash = hash_password(password)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s) RETURNING id", (full_name, email, pwd_hash))
        user_id = cursor.fetchone()['id']
        conn.commit()
    except psycopg2.IntegrityError:
        conn.close()
        return jsonify({"error": "This email is already registered."}), 409
    finally:
        conn.close()
        
    access_token = generate_access_token(user_id, email)
    refresh_token = generate_refresh_token(user_id, user_agent, ip_address)
    session_id = create_session(user_id, user_agent, ip_address)
    csrf_token = generate_csrf_token(session_id)
    verify_token = generate_email_verification_token(user_id)
    
    email_sent = send_email(redis_client, REDIS_AVAILABLE, email, "Verify your SAAITA account", f"Please verify your email: <a href='{APP_URL}/verify-email?token={verify_token}'>Verify Email</a>")
    
    audit_log("USER_SIGNUP", user_id=user_id, ip_address=ip_address, user_agent=user_agent)
    resp = jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
        "user": {
            "id": user_id, "full_name": full_name, "email": email,
            "is_onboarded": False, "is_verified": False
        }
    })
    set_auth_cookies(resp, access_token, refresh_token, csrf_token)
    return resp, 201

@auth_bp.route("/login", methods=["POST"])
@limiter.limit(LOGIN_LIMIT)
def login():
    ip_address = get_ip()
    user_agent = get_ua()
    if request.content_length and request.content_length > MAX_JSON:
        return jsonify({"error": "Request payload too large."}), 413
        
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
        
    ok, msg = validate_schema(data, "login")
    if not ok: return jsonify({"error": msg}), 400
    
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    ok, msg = validate_email(email)
    if not ok: return jsonify({"error": msg}), 400
    
    locked, lock_msg = check_brute_force(email, ip_address)
    if locked:
        audit_log("LOGIN_BLOCKED", ip_address=ip_address, details=email, level="WARN")
        return jsonify({"error": lock_msg}), 429
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, password_hash, is_onboarded, is_verified FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        # Run dummy hash to equalize response time — prevents user enumeration via timing
        verify_password(DUMMY_HASH, password)
        record_login_attempt(email, ip_address, False, user_agent)
        audit_log("LOGIN_FAILED", ip_address=ip_address, details=email, level="WARN")
        time.sleep(0.1)
        return jsonify({"error": "Invalid email or password."}), 401

    if not verify_password(row["password_hash"], password):
        record_login_attempt(email, ip_address, False, user_agent)
        audit_log("LOGIN_FAILED", ip_address=ip_address, details=email, level="WARN")
        time.sleep(0.1)
        return jsonify({"error": "Invalid email or password."}), 401
        
    record_login_attempt(email, ip_address, True, user_agent)
    # Destroy all existing sessions to prevent session fixation attacks
    invalidate_all_sessions(row["id"])
    revoke_all_refresh_tokens(row["id"])
    access_token = generate_access_token(row["id"], email)
    refresh_token = generate_refresh_token(row["id"], user_agent, ip_address)
    session_id = create_session(row["id"], user_agent, ip_address)
    csrf_token = generate_csrf_token(session_id)
    
    audit_log("USER_LOGIN", user_id=row["id"], ip_address=ip_address, user_agent=user_agent, session_id=session_id)
    resp = jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
        "user": {
            "id": row["id"], "full_name": row["full_name"], "email": email,
            "is_onboarded": bool(row["is_onboarded"]), "is_verified": bool(row["is_verified"])
        }
    })
    set_auth_cookies(resp, access_token, refresh_token, csrf_token)
    return resp

@auth_bp.route("/refresh", methods=["POST"])
@limiter.limit(REFRESH_LIMIT)
def refresh_token_route():
    data = request.json or {}
    refresh_token_str = data.get("refresh_token", "") or request.cookies.get("refresh_token", "")
    if not refresh_token_str:
        return jsonify({"error": "Refresh token required."}), 401
        
    result = refresh_access_token(refresh_token_str)
    if result is None:
        return jsonify({"error": "Refresh failed"}), 401
        
    new_access_token, user_data = result
    if not new_access_token:
        return jsonify({"error": user_data}), 401
        
    csrf_token = generate_csrf_token()
    resp = jsonify({
        "access_token": new_access_token,
        "csrf_token": csrf_token,
        "user": user_data
    })
    resp.set_cookie("access_token", new_access_token, httponly=True, secure=request.is_secure, samesite="Strict", path="/", max_age=900)
    resp.set_cookie("csrf_token", csrf_token, httponly=False, secure=request.is_secure, samesite="Lax", path="/")
    return resp

@auth_bp.route("/me", methods=["GET"])
@require_auth
def me(user):
    return jsonify({"user": user})

@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout(user):
    revoke_all_refresh_tokens(user["id"])
    invalidate_all_sessions(user["id"])
    audit_log("USER_LOGOUT", user_id=user["id"], ip_address=get_ip())
    resp = jsonify({"message": "Logged out successfully."})
    resp.set_cookie("access_token", "", expires=0, path="/")
    resp.set_cookie("refresh_token", "", expires=0, path="/api/auth/refresh")
    resp.set_cookie("csrf_token", "", expires=0, path="/")
    return resp

@auth_bp.route("/onboarding", methods=["POST"])
@require_auth
def complete_onboarding(user):
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_onboarded = TRUE, onboarding_data = %s WHERE id = %s", (json.dumps(data), user["id"]))
        conn.commit()
    finally:
        conn.close()
    audit_log("ONBOARDING_COMPLETE", user_id=user["id"], ip_address=get_ip())
    return jsonify({"message": "Onboarding completed.", "user": {**user, "is_onboarded": True}})

@auth_bp.route("/change-password", methods=["POST"])
@require_auth
@csrf_protect
def change_password(user):
    data = request.json or {}
    ok, msg = validate_schema(data, "change_password")
    if not ok: return jsonify({"error": msg}), 400
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    ok, msg = validate_password(new_password)
    if not ok: return jsonify({"error": msg}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    row = cursor.fetchone()
    conn.close()
    
    if not verify_password(row["password_hash"], current_password):
        return jsonify({"error": "Current password is incorrect."}), 401
        
    new_hash = hash_password(new_password)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s", (new_hash, datetime.now(timezone.utc).isoformat(), user["id"]))
        conn.commit()
    finally:
        conn.close()
        
    revoke_all_refresh_tokens(user["id"])
    invalidate_all_sessions(user["id"])
    audit_log("PASSWORD_CHANGED", user_id=user["id"], ip_address=get_ip(), level="WARN")
    return jsonify({"message": "Password changed successfully."})

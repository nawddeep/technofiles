"""SAAITA Backend - Security Hardened"""
import re, json, base64, psycopg2, uuid, os, secrets, html, time, logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from database import init_db, get_db, cleanup_expired_data
import jwt as pyjwt
import redis

load_dotenv()
# FIX 2.15: Single ENVIRONMENT variable (development/staging/production) replaces dual FLASK_DEBUG + FLASK_ENV
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
VALID_ENVIRONMENTS = {"development", "staging", "production"}
if ENVIRONMENT not in VALID_ENVIRONMENTS:
    raise SystemExit(f"[FATAL] ENVIRONMENT must be one of {VALID_ENVIRONMENTS}, got: {ENVIRONMENT}")
DEBUG = ENVIRONMENT == "development"
IS_PRODUCTION = ENVIRONMENT == "production"

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",")] if os.getenv("ALLOWED_ORIGINS") else []
if not ALLOWED_ORIGINS:
    raise SystemExit("[FATAL] ALLOWED_ORIGINS must be set in .env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@saaita.com")
APP_URL = os.getenv("APP_URL", "http://localhost:5173")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SAAITA")

if not JWT_SECRET_KEY:
    raise SystemExit("[FATAL] JWT_SECRET_KEY required - set in .env")
if len(JWT_SECRET_KEY) < 32:
    raise SystemExit("[FATAL] JWT_SECRET_KEY must be >= 32 chars")

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("[OK] Redis connected")
except Exception as e:
    raise SystemExit(f"[FATAL] Redis connection failed: {e}")

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri=REDIS_URL)

# FIX 2.17: API Versioning - register routes at /api/v1/... (current) and /api/... (legacy for backward compatibility)
def versioned_route(path, methods=["GET"], limit=None):
    """Registers route at both /api/v1/path and /api/path for backward compatibility"""
    def decorator(func):
        @app.route(f"/api/v1{path}", methods=methods)
        @app.route(f"/api{path}", methods=methods)
        def versioned_endpoint(*args, **kwargs):
            return func(*args, **kwargs)
        
        if limit:
            versioned_endpoint = limiter.limit(limit)(versioned_endpoint)
        
        return func  # Return original function
    return decorator

# AI Sessions now use Redis instead of in-memory dict
ai_sessions = {}

# === CONSTANTS ===
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PWD_MIN = 12
MAX_JSON = 1048576
MAX_FILE = 5242880
ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

SCHEMAS = {
    "signup": {
        "fullName": {"type": "string", "required": True, "min_length": 1, "max_length": 100},
        "email": {"type": "string", "required": True, "min_length": 3, "max_length": 254},
        "password": {"type": "string", "required": True, "min_length": 12, "max_length": 128}
    },
    "login": {
        "email": {"type": "string", "required": True, "min_length": 3, "max_length": 254},
        "password": {"type": "string", "required": True, "min_length": 1, "max_length": 128}
    },
    "chat_message": {
        "prompt": {"type": "string", "required": False, "min_length": 0, "max_length": 10000},
        "images": {"type": "array", "required": False, "max_length": 5}
    },
    "change_password": {
        "current_password": {"type": "string", "required": True, "min_length": 1, "max_length": 128},
        "new_password": {"type": "string", "required": True, "min_length": 12, "max_length": 128}
    },
    "password_reset_request": {
        "email": {"type": "string", "required": True, "min_length": 3, "max_length": 254}
    },
    "password_reset_confirm": {
        "token": {"type": "string", "required": True, "min_length": 1, "max_length": 256},
        "new_password": {"type": "string", "required": True, "min_length": 12, "max_length": 128}
    },
    "email_verification": {
        "token": {"type": "string", "required": True, "min_length": 1, "max_length": 256}
    },
    "refresh_token": {
        "refresh_token": {"type": "string", "required": True, "min_length": 1, "max_length": 1024}
    },
}


# === INPUT VALIDATION ===
def sanitize_input(data):
    if isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(i) for i in data]
    elif isinstance(data, str):
        return html.escape(data.strip(), quote=True)
    return data


def has_null_bytes(data):
    if isinstance(data, str):
        return "\x00" in data
    elif isinstance(data, dict):
        return any(has_null_bytes(v) for v in data.values())
    elif isinstance(data, list):
        return any(has_null_bytes(i) for i in data)
    return False


def validate_email(email):
    if not email or not isinstance(email, str):
        return False, "Email is required."
    email = email.strip().lower()
    if len(email) > 254:
        return False, "Email is too long."
    if not EMAIL_RE.match(email):
        return False, "Invalid email format."
    return True, ""


def validate_password(password):
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < PWD_MIN:
        return False, f"Password must be at least {PWD_MIN} characters."
    if not any(c.isupper() for c in password):
        return False, "Password must contain an uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain a lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain a number."
    special_chars = set("!@#$%^&*()_+-=[]{}|;':\",./<>?`~")
    if not any(c in special_chars for c in password):
        return False, "Password must contain a special character."
    return True, ""


def validate_schema(data, schema_name):
    if schema_name not in SCHEMAS:
        return True, ""
    schema = SCHEMAS[schema_name]
    errors = []
    if isinstance(data, dict):
        unknown = set(data.keys()) - set(schema.keys())
        if unknown:
            errors.append("Unknown fields: " + ", ".join(sorted(unknown)))
    for field_name, rules in schema.items():
        val = data.get(field_name) if isinstance(data, dict) else None
        if rules.get("required") and (val is None or val == ""):
            errors.append(f"Field '{field_name}' is required.")
            continue
        if val is None:
            continue
        expected_type = rules.get("type")
        if expected_type == "string" and not isinstance(val, str):
            errors.append(f"Field '{field_name}' must be a string.")
        elif expected_type == "array" and not isinstance(val, list):
            errors.append(f"Field '{field_name}' must be an array.")
        if isinstance(val, str):
            if len(val) < rules.get("min_length", 0):
                errors.append(f"Field '{field_name}' is too short.")
            if len(val) > rules.get("max_length", float("inf")):
                errors.append(f"Field '{field_name}' is too long.")
        if isinstance(val, list) and len(val) > rules.get("max_length", float("inf")):
            errors.append(f"Field '{field_name}' has too many items.")
    return (False, " ".join(errors)) if errors else (True, "")


def validate_file_upload(file_storage):
    if not file_storage:
        return False, "No file provided."
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_FILE:
        return False, "File size exceeds 5MB limit."
    mime_type = file_storage.content_type
    if mime_type not in ALLOWED_MIME:
        return False, f"File type {mime_type} is not allowed."
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return False, f"File extension {ext} is not allowed."
    mime_to_ext = {
        "image/jpeg": {".jpg", ".jpeg"},
        "image/png": {".png"},
        "image/gif": {".gif"},
        "image/webp": {".webp"}
    }
    if ext not in mime_to_ext.get(mime_type, set()):
        return False, "File extension does not match MIME type."
    return True, ""


def scan_file_content(file_bytes):
    # FIX 1.9: Scan ENTIRE file, not just first 4KB
    try:
        text = file_bytes.decode("utf-8", errors="ignore").lower()  # Scan full content
        malicious_patterns = [
            "<script", "javascript:", "onerror=", "onload=",
            "<?php", "eval(", "document.cookie"
        ]
        for pattern in malicious_patterns:
            if pattern in text:
                return False, "Potentially malicious content detected."
    except Exception:
        pass
    executable_sigs = [b"MZ", b"\x7fELF"]
    for sig in executable_sigs:
        if sample.startswith(sig):
            return False, "Executable files are not allowed."
    return True, ""


# === JWT AUTH ===
def generate_access_token(user_id, email):
    payload = {
        "user_id": user_id, "email": email, "type": "access",
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


# === PASSWORD HASHING ===
try:
    from argon2 import PasswordHasher, Type
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    ARGON2_AVAILABLE = True
except ImportError:
    logger.error("[FATAL] argon2-cffi not installed. Run: pip install argon2-cffi")
    raise SystemExit("[FATAL] argon2-cffi is required. Install with: pip install argon2-cffi")


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


# === AUTH DECORATORS ===
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # FIX 1.6: Check httpOnly cookie first (browser clients), then Authorization header (API clients)
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
        cursor.execute(
            "SELECT id, full_name, email, is_onboarded, is_verified, onboarding_data, created_at FROM users WHERE id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "User not found."}), 401
        user = {
            "id": row["id"], "full_name": row["full_name"], "email": row["email"],
            "is_onboarded": bool(row["is_onboarded"]), "is_verified": bool(row["is_verified"]),
            "onboarding_data": row["onboarding_data"] or "",
            "member_since": row["created_at"].isoformat()[:10] if row["created_at"] else "\u2014"
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


def get_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def get_ua():
    return request.headers.get("User-Agent", "Unknown")


# === CSRF PROTECTION ===

def generate_csrf_token(session_id=""):
    token = secrets.token_urlsafe(32)
    redis_client.setex(f"csrf:{token}", 3600, session_id)  # 1 hour TTL
    return token


def validate_csrf_token(token):
    return redis_client.exists(f"csrf:{token}") > 0


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


# === AUDIT LOGGING ===
def audit_log(event_type, user_id=None, ip_address=None, user_agent=None,
              resource_type=None, resource_id=None, action=None,
              details=None, session_id=None, level="INFO"):
    # FIX 1.10: Raise exception if audit log fails (don't silently drop security events)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (level, event_type, user_id, ip_address, user_agent, resource_type, resource_id, action, details, session_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (level, event_type, user_id, ip_address, user_agent, resource_type, resource_id, action, details, session_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"[CRITICAL] Audit log failed: {e}")
        raise SystemExit(f"[FATAL] Audit logging failed - security event not recorded: {e}")
    finally:
        conn.close()


# === BRUTE FORCE PROTECTION ===
def record_login_attempt(email, ip_address, success, user_agent=""):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO login_attempts (email, ip_address, success, user_agent) VALUES (%s, %s, %s, %s)",
            (email, ip_address, success, user_agent)
        )
        conn.commit()
    finally:
        conn.close()


def check_brute_force(email, ip_address):
    conn = get_db()
    cursor = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    if email:
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM login_attempts WHERE email = %s AND success = FALSE AND timestamp > %s",
            (email, cutoff)
        )
        email_count = cursor.fetchone()['cnt']
        if email_count >= 5:
            conn.close()
            return True, "Account temporarily locked. Try again in 15 minutes."
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM login_attempts WHERE ip_address = %s AND success = FALSE AND timestamp > %s",
        (ip_address, cutoff)
    )
    ip_count = cursor.fetchone()['cnt']
    if ip_count >= 10:
        conn.close()
        return True, "Too many failed attempts from this IP."
    conn.close()
    return False, ""


# === SESSION MANAGEMENT ===
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


def get_user_sessions(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_id, created_at, user_agent, ip_address FROM sessions WHERE user_id = %s AND is_active = TRUE",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# === EMAIL ===
def send_email(to_address, subject, body):
    if not SMTP_HOST or not SMTP_USER:
        logger.info(f"[EMAIL] Would send to {to_address}: {subject}")
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, to_address, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def generate_password_reset_token(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE password_reset_tokens SET is_used = TRUE WHERE user_id = %s AND is_used = FALSE", (user_id,))
        cursor.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (user_id, token, expires_at.isoformat())
        )
        conn.commit()
    finally:
        conn.close()
    return token


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


# === SECURITY ALERTS ===
def create_security_alert(severity, alert_type, description, ip_address=None, user_id=None, details=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO security_alerts (severity, alert_type, description, ip_address, user_id, details) VALUES (%s, %s, %s, %s, %s, %s)",
            (severity, alert_type, description, ip_address, user_id, details)
        )
        conn.commit()
        conn.close()
        logger.warning(f"[SECURITY ALERT] [{severity}] {alert_type}: {description}")
    except Exception as e:
        logger.error(f"Security alert creation failed: {e}")


# === SECURITY HEADERS ===
@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    else:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


def set_auth_cookies(response, access_token, refresh_token, csrf_token):
    secure = request.is_secure
    # Use Lax for development (allows cross-origin), Strict for production
    samesite = "Lax" if ENVIRONMENT == "development" else "Strict"
    response.set_cookie("access_token", access_token, httponly=True, secure=secure, samesite=samesite, path="/", max_age=900)
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=secure, samesite=samesite, path="/api/auth/refresh", max_age=604800)
    response.set_cookie("csrf_token", csrf_token, httponly=False, secure=secure, samesite="Lax", path="/")
    return response


# === GEMINI AI ===
def get_gemini_model(user_profile=""):
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            base_instruction = f.read().strip()
        full_instruction = base_instruction
        if user_profile:
            full_instruction += f"\n\nUSER PROFILE: {user_profile}"
        return genai.GenerativeModel("gemini-2.0-flash", system_instruction=full_instruction)
    except Exception as e:
        logger.error(f"Gemini model init error: {e}")
        return None


def explain_image_with_gemini(image_bytes, mime_type="image/jpeg"):
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([
            "Describe this image in detail so another language model can understand its contents.",
            {"mime_type": mime_type, "data": image_bytes}
        ])
        return response.text
    except Exception as e:
        return f"(Image processing failed: {e})"


def get_or_create_ai_session(session_id, user_id, onboarding_data=""):
    # Try to get from Redis first
    cached = redis_client.get(f"ai_session:{session_id}")
    if cached:
        return json.loads(cached)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, text FROM chat_messages WHERE user_id = %s ORDER BY created_at ASC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    formatted_history = []
    for row in rows:
        role = "user" if row["sender"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [row["text"]]})
    
    model = get_gemini_model(onboarding_data or "")
    if model is None:
        return None
    
    chat = model.start_chat(history=formatted_history)
    new_group_id = str(uuid.uuid4())
    
    session_data = {
        "chat_group_id": new_group_id,
        "user_id": user_id
    }
    # Store in Redis with 24-hour TTL, keep chat object in memory (can't serialize)
    redis_client.setex(f"ai_session:{session_id}", 86400, json.dumps(session_data))
    
    # Keep in-memory for the chat object (Gemini client can't be serialized)
    ai_sessions[session_id] = {
        "chat": chat,
        "chat_group_id": new_group_id,
        "user_id": user_id
    }
    return ai_sessions[session_id]


# =========================================================
# AUTH ROUTES
# =========================================================

@app.route("/api/auth/csrf-token", methods=["GET"])
@app.route("/api/v1/auth/csrf-token", methods=["GET"])  # FIX 2.17: Versioned endpoint
def get_csrf_token_route():
    token = generate_csrf_token()
    resp = jsonify({"csrf_token": token})
    resp.set_cookie("csrf_token", token, samesite="Lax", httponly=False, secure=request.is_secure, path="/")
    return resp


@app.route("/api/auth/signup", methods=["POST"])
@app.route("/api/v1/auth/signup", methods=["POST"])  # FIX 2.17: Versioned endpoint
@limiter.limit("100 per hour")  # Increased from 3 for development testing
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
    if not ok:
        return jsonify({"error": msg}), 400
    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400
    pwd_hash = hash_password(password)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (full_name, email, pwd_hash)
        )
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
    email_sent = send_email(email, "Verify your SAAITA account",
               f"Please verify your email: <a href='{APP_URL}/verify-email?token={verify_token}'>Verify Email</a>")
    if not email_sent:
        logger.warning(f"[SIGNUP] Email verification failed for {email}")
        return jsonify({"error": "Email service unavailable. Please try again later or contact support."}), 503
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


@app.route("/api/auth/login", methods=["POST"])
@app.route("/api/v1/auth/login", methods=["POST"])  # FIX 2.17: Versioned endpoint
@limiter.limit("5 per 15 minutes")
def login():
    ip_address = get_ip()
    user_agent = get_ua()
    if request.content_length and request.content_length > MAX_JSON:
        return jsonify({"error": "Request payload too large."}), 413
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
    ok, msg = validate_schema(data, "login")
    if not ok:
        return jsonify({"error": msg}), 400
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    ok, msg = validate_email(email)
    if not ok:
        return jsonify({"error": msg}), 400
    locked, lock_msg = check_brute_force(email, ip_address)
    if locked:
        audit_log("LOGIN_BLOCKED", ip_address=ip_address, details=email, level="WARN")
        return jsonify({"error": lock_msg}), 429
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, password_hash, is_onboarded, is_verified FROM users WHERE email = %s",
        (email,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not verify_password(row["password_hash"], password):
        record_login_attempt(email, ip_address, False, user_agent)
        audit_log("LOGIN_FAILED", ip_address=ip_address, details=email, level="WARN")
        time.sleep(0.1)
        return jsonify({"error": "Invalid email or password."}), 401
    record_login_attempt(email, ip_address, True, user_agent)
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


@app.route("/api/auth/refresh", methods=["POST"])
@limiter.limit("20 per hour")
def refresh_token_route():
    data = request.json or {}
    refresh_token_str = data.get("refresh_token", "") or request.cookies.get("refresh_token", "")
    if not refresh_token_str:
        return jsonify({"error": "Refresh token required."}), 401
    new_access_token, user_data = refresh_access_token(refresh_token_str)
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


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me(user):
    return jsonify({"user": user})


@app.route("/api/auth/logout", methods=["POST"])
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


@app.route("/api/auth/onboarding", methods=["POST"])
@require_auth
# @require_verified_email  # Allow onboarding before email verification
def complete_onboarding(user):
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_onboarded = TRUE, onboarding_data = %s WHERE id = %s",
            (json.dumps(data), user["id"])
        )
        conn.commit()
    finally:
        conn.close()
    audit_log("ONBOARDING_COMPLETE", user_id=user["id"], ip_address=get_ip())
    return jsonify({"message": "Onboarding completed.", "user": {**user, "is_onboarded": True}})


@app.route("/api/auth/change-password", methods=["POST"])
@require_auth
@csrf_protect
def change_password(user):
    data = request.json or {}
    ok, msg = validate_schema(data, "change_password")
    if not ok:
        return jsonify({"error": msg}), 400
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    ok, msg = validate_password(new_password)
    if not ok:
        return jsonify({"error": msg}), 400
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
        cursor.execute(
            "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
            (new_hash, datetime.now(timezone.utc).isoformat(), user["id"])
        )
        conn.commit()
    finally:
        conn.close()
    revoke_all_refresh_tokens(user["id"])
    invalidate_all_sessions(user["id"])
    audit_log("PASSWORD_CHANGED", user_id=user["id"], ip_address=get_ip(), level="WARN")
    return jsonify({"message": "Password changed successfully."})


@app.route("/api/auth/forgot-password", methods=["POST"])
@limiter.limit("3 per hour")
def forgot_password():
    data = request.json or {}
    ok, msg = validate_schema(data, "password_reset_request")
    if not ok:
        return jsonify({"error": msg}), 400
    email = data.get("email", "").strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    if row:
        token = generate_password_reset_token(row["id"])
        send_email(email, "Reset your SAAITA password",
                   f"Click to reset: <a href='{APP_URL}/reset-password?token={token}'>Reset Password</a>")
    conn.close()
    audit_log("PASSWORD_RESET_REQUESTED", ip_address=get_ip(), details="email_provided")
    return jsonify({"message": "If that email exists, a reset link has been sent."})


@app.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("3 per hour")
def reset_password():
    data = request.json or {}
    ok, msg = validate_schema(data, "password_reset_confirm")
    if not ok:
        return jsonify({"error": msg}), 400
    token = data.get("token", "")
    new_password = data.get("new_password", "")
    ok, msg = validate_password(new_password)
    if not ok:
        return jsonify({"error": msg}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, is_used, expires_at FROM password_reset_tokens WHERE token = %s",
        (token,)
    )
    row = cursor.fetchone()
    if not row or row["is_used"] or datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
        conn.close()
        return jsonify({"error": "Invalid or expired reset token."}), 400
    user_id = row["user_id"]
    cursor.execute("UPDATE password_reset_tokens SET is_used = TRUE WHERE id = %s", (row["id"],))
    new_hash = hash_password(new_password)
    cursor.execute(
        "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
        (new_hash, datetime.now(timezone.utc).isoformat(), user_id)
    )
    conn.commit()
    conn.close()
    revoke_all_refresh_tokens(user_id)
    invalidate_all_sessions(user_id)
    audit_log("PASSWORD_RESET_COMPLETED", user_id=user_id, ip_address=get_ip(), level="WARN")
    return jsonify({"message": "Password reset successfully."})


@app.route("/api/auth/verify-email", methods=["POST"])
@limiter.limit("3 per hour")
def verify_email_route():
    data = request.json or {}
    ok, msg = validate_schema(data, "email_verification")
    if not ok:
        return jsonify({"error": msg}), 400
    token = data.get("token", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, is_used, expires_at FROM email_verification_tokens WHERE token = %s",
        (token,)
    )
    row = cursor.fetchone()
    if not row or row["is_used"] or datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
        conn.close()
        return jsonify({"error": "Invalid or expired verification token."}), 400
    cursor.execute("UPDATE email_verification_tokens SET is_used = TRUE WHERE id = %s", (row["id"],))
    cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (row["user_id"],))
    conn.commit()
    conn.close()
    audit_log("EMAIL_VERIFIED", user_id=row["user_id"], ip_address=get_ip())
    return jsonify({"message": "Email verified successfully."})


@app.route("/api/auth/resend-verification", methods=["POST"])
@limiter.limit("3 per hour")
def resend_verification():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required."}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    if row and not row["is_verified"]:
        token = generate_email_verification_token(row["id"])
        send_email(email, "Verify your SAAITA account",
                   f"Verify: <a href='{APP_URL}/verify-email?token={token}'>Verify Email</a>")
    conn.close()
    return jsonify({"message": "If that email exists and is unverified, a new verification link has been sent."})


@app.route("/api/auth/sessions", methods=["GET"])
@require_auth
def list_sessions(user):
    return jsonify({"sessions": get_user_sessions(user["id"])})


@app.route("/api/auth/sessions/<session_id>/revoke", methods=["POST"])
@require_auth
@csrf_protect
def revoke_session(user, session_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET is_active = FALSE WHERE session_id = %s AND user_id = %s",
            (session_id, user["id"])
        )
        conn.commit()
    finally:
        conn.close()
    audit_log("SESSION_REVOKED", user_id=user["id"], ip_address=get_ip(), details=session_id)
    return jsonify({"message": "Session revoked."})


# =========================================================
# CHAT ROUTES
# =========================================================

@app.route("/api/chat/message", methods=["POST"])
@require_auth
# @require_verified_email  # Allow chat before email verification (for testing)
@limiter.limit("30 per minute")
def chat_message(user):
    if not GEMINI_API_KEY:
        return jsonify({"error": "AI service is not configured."}), 503
    data = request.json or {}
    if has_null_bytes(data):
        return jsonify({"error": "Invalid input data."}), 400
    prompt = data.get("prompt", "").strip()
    images = data.get("images", [])
    if not prompt and not images:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(prompt) > 10000:
        return jsonify({"error": "Message too long."}), 400
    session_id = request.headers.get("X-Session-Id", str(user["id"]))
    ai_sess = get_or_create_ai_session(session_id, user["id"], user.get("onboarding_data", ""))
    if ai_sess is None:
        return jsonify({"error": "Failed to initialize AI."}), 503
    image_context = ""
    db_prompt = prompt
    if images:
        descriptions = []
        for idx, img in enumerate(images[:5]):
            try:
                img_bytes = base64.b64decode(img["data"])
                if len(img_bytes) > MAX_FILE:
                    descriptions.append(f"Image {idx+1}: (too large)")
                    continue
                ok, msg = scan_file_content(img_bytes)
                if not ok:
                    descriptions.append(f"Image {idx+1}: (rejected - {msg})")
                    continue
                desc = explain_image_with_gemini(img_bytes, img.get("mime_type", "image/jpeg"))
                descriptions.append(f"Image {idx+1}: {desc}")
            except Exception:
                descriptions.append(f"Image {idx+1}: (failed to process)")
        image_context = "\n\n[System: User attached images.]\n" + "\n".join(descriptions)
        db_prompt += f" [{len(images)} image(s)]"
    final_prompt = prompt + image_context
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (user_id, sender, text, chat_group_id) VALUES (%s, %s, %s, %s)",
            (user["id"], "user", db_prompt, ai_sess["chat_group_id"])
        )
        conn.commit()
    finally:
        conn.close()
    try:
        response = ai_sess["chat"].send_message(final_prompt)
        ai_text = response.text
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (user_id, sender, text, chat_group_id) VALUES (%s, %s, %s, %s)",
                (user["id"], "ai", ai_text, ai_sess["chat_group_id"])
            )
            conn.commit()
        finally:
            conn.close()
        audit_log("CHAT_MESSAGE", user_id=user["id"], ip_address=get_ip(), resource_type="chat")
        return jsonify({"text": ai_text})
    except Exception as e:
        logger.error(f"AI error: {e}")
        return jsonify({"error": "An error occurred processing your message."}), 500


@app.route("/api/chat/history", methods=["GET"])
@require_auth
# @require_verified_email  # Allow history before email verification
def chat_history(user):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, text FROM chat_messages WHERE user_id = %s ORDER BY created_at ASC",
        (user["id"],)
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"messages": [{"sender": r["sender"], "text": r["text"]} for r in rows]})


@app.route("/api/chat/clear", methods=["POST"])
@require_auth
# @require_verified_email  # Allow clear before email verification
def chat_clear(user):
    new_group_id = str(uuid.uuid4())
    session_id = request.headers.get("X-Session-Id", str(user["id"]))
    if session_id in ai_sessions:
        ai_sess = ai_sessions[session_id]
        ai_sess["chat_group_id"] = new_group_id
        model = get_gemini_model(user.get("onboarding_data", ""))
        if model:
            ai_sess["chat"] = model.start_chat(history=[])
    return jsonify({"success": True, "chat_group_id": new_group_id})


# =========================================================
# FILE UPLOAD
# =========================================================

@app.route("/api/upload", methods=["POST"])
@app.route("/api/v1/upload", methods=["POST"])  # FIX 2.17: Versioned endpoint
@require_auth
# @require_verified_email  # Allow upload before email verification
@limiter.limit("10 per hour")
def upload_file(user):
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400
    file = request.files["file"]
    ok, msg = validate_file_upload(file)
    if not ok:
        return jsonify({"error": msg}), 400
    file_bytes = file.read()
    ok, msg = scan_file_content(file_bytes)
    if not ok:
        return jsonify({"error": msg}), 400
    stored_name = str(uuid.uuid4()) + os.path.splitext(file.filename)[1].lower()
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO file_uploads (user_id, original_filename, stored_filename, file_path, file_size, mime_type) VALUES (%s, %s, %s, %s, %s, %s)",
            (user["id"], file.filename, stored_name, file_path, len(file_bytes), file.content_type)
        )
        conn.commit()
    finally:
        conn.close()
    audit_log("FILE_UPLOAD", ip_address=get_ip(), resource_type="file")
    return jsonify({"message": "File uploaded.", "filename": stored_name}), 201


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many requests. Please wait."}), 429


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error."}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Request payload too large."}), 413


@app.before_request
def before_request_cleanup():
    if secrets.randbelow(1000) == 0:
        try:
            cleanup_expired_data()
        except Exception:
            pass


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    # FIX 1.6: Verify PostgreSQL is configured
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("[FATAL] DATABASE_URL not set in .env - PostgreSQL required")
    
    init_db()
    if not GEMINI_API_KEY:
        print("\n[WARNING] GEMINI_API_KEY not set - AI chat disabled!\n")
    else:
        print("\n[OK] GEMINI_API_KEY loaded - AI chat enabled\n")
    print("[OK] Security features enabled: JWT Auth, CSRF, Rate Limiting,")
    print("     Brute Force Protection, Audit Logging, Security Headers,")
    print("     Input Validation, Secure Cookies, Email Verification,")
    print("     Password Reset, Session Management, File Upload Security")
    app.run(port=5000, debug=DEBUG)

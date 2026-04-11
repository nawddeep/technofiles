import re
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db

# --- Read config from environment ---
import os
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176"
).split(",")

app = Flask(__name__)

CORS(app, supports_credentials=True, resources={
    r"/api/*": {"origins": ALLOWED_ORIGINS}
})

# Rate limiter — uses in-memory store (fine for dev/single-server prod)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# --- Constants ---
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
PASSWORD_MIN_LENGTH = 8
SESSION_DURATION_DAYS = 7


# --- Helpers ---

def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter."
    return True, ""


def create_session(user_id: int) -> str:
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
        (session_id, user_id, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return session_id


def get_session_user(session_id: str):
    conn = get_db()
    row = conn.execute("""
        SELECT u.id, u.full_name, u.email, u.created_at, u.is_onboarded, s.expires_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_id = ?
    """, (session_id,)).fetchone()

    if not row:
        conn.close()
        return None

    # Check expiry
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.utcnow() > expires_at:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        return None

    # Count active sessions for this user
    active_sessions = conn.execute(
        "SELECT COUNT(*) as cnt FROM sessions WHERE user_id = ? AND expires_at > ?",
        (row["id"], datetime.utcnow().isoformat())
    ).fetchone()["cnt"]

    conn.close()
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "member_since": row["created_at"][:10] if row["created_at"] else "—",
        "active_sessions": active_sessions,
        "is_onboarded": bool(row["is_onboarded"])
    }


# --- Routes ---

@app.route("/api/auth/signup", methods=["POST"])
@limiter.limit("5 per minute")
def signup():
    data = request.json or {}
    full_name = data.get("fullName", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not full_name or not email or not password:
        return jsonify({"error": "All fields are required."}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400

    pwd_hash = generate_password_hash(password)

    try:
        conn = get_db()
        c = conn.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name, email, pwd_hash)
        )
        user_id = c.lastrowid
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered."}), 409

    session_id = create_session(user_id)
    return jsonify({
        "session_id": session_id,
        "user": {"id": user_id, "full_name": full_name, "email": email}
    }), 201


@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT id, full_name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    # Vague error to avoid leaking whether the email exists
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session_id = create_session(row["id"])
    return jsonify({
        "session_id": session_id,
        "user": {"id": row["id"], "full_name": row["full_name"], "email": email}
    })


@app.route("/api/auth/me", methods=["GET"])
def me():
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        return jsonify({"error": "No session provided."}), 401

    user = get_session_user(session_id)
    if not user:
        return jsonify({"error": "Session expired or invalid."}), 401

    return jsonify({"user": user})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session_id = request.headers.get("X-Session-Id")
    if session_id:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    return jsonify({"message": "Logged out successfully."})


@app.route("/api/auth/onboarding", methods=["POST"])
def complete_onboarding():
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        return jsonify({"error": "No session provided."}), 401
    
    user = get_session_user(session_id)
    if not user:
        return jsonify({"error": "Session expired or invalid."}), 401
        
    data = request.json or {}
    
    conn = get_db()
    conn.execute(
        "UPDATE users SET is_onboarded = 1, onboarding_data = ? WHERE id = ?",
        (json.dumps(data), user["id"])
    )
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Onboarding completed successfully.", "user": {**user, "is_onboarded": True}})


# Return 429 JSON instead of HTML when rate limit is hit
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many attempts. Please wait a moment and try again."}), 429


if __name__ == "__main__":
    init_db()
    app.run(port=5000, debug=FLASK_DEBUG)

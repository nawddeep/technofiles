"""SAAITA Backend - Refactored Structure"""
import os
import secrets
import logging
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from database import init_db, cleanup_expired_data
from extensions import init_redis, init_limiter
from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp
from routes.upload_routes import upload_bp
from services.queue_service import load_email_queue_from_file, retry_queued_emails
from extensions import redis_client, REDIS_AVAILABLE

load_dotenv()

# Env validation
required_vars = ["DATABASE_URL", "JWT_SECRET_KEY", "GEMINI_API_KEY"]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    raise SystemExit(f"Missing required environment variables: {missing}")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
VALID_ENVIRONMENTS = {"development", "staging", "production"}
if ENVIRONMENT not in VALID_ENVIRONMENTS:
    raise SystemExit(f"[FATAL] ENVIRONMENT must be one of {VALID_ENVIRONMENTS}, got: {ENVIRONMENT}")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",")] if os.getenv("ALLOWED_ORIGINS") else []
if not ALLOWED_ORIGINS:
    raise SystemExit("[FATAL] ALLOWED_ORIGINS must be set in .env")

# Payload limits from environment (can be tuned without code changes)
MAX_JSON = int(os.getenv("MAX_JSON_SIZE", "1048576"))   # 1 MB default
MAX_FILE = int(os.getenv("MAX_FILE_SIZE", "5242880"))   # 5 MB default

# Gemini key basic sanity check
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY and len(GEMINI_API_KEY) < 20:
    logger.warning("[WARN] GEMINI_API_KEY looks too short — it may be invalid")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SAAITA")

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

# Initialize extensions
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
init_redis(redis_url)
init_limiter(app, redis_url)

# Load queue
load_email_queue_from_file()
def queue_worker():
    while True:
        retry_queued_emails(redis_client, REDIS_AVAILABLE)
        time.sleep(60)

# Register Blueprints with explicit v1 and aliased structure
app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
app.register_blueprint(auth_bp, url_prefix="/api/auth", name="auth_legacy") # legacy
app.register_blueprint(chat_bp, url_prefix="/api/v1/chat")
app.register_blueprint(chat_bp, url_prefix="/api/chat", name="chat_legacy") # legacy
app.register_blueprint(upload_bp, url_prefix="/api/v1")
app.register_blueprint(upload_bp, url_prefix="/api", name="upload_legacy") # legacy

@app.route("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.before_request
def before_request_hook():
    # Enforce HTTPS in production — reject plaintext HTTP requests
    if IS_PRODUCTION and not request.is_secure:
        return jsonify({"error": "HTTPS is required."}), 403
    # Randomly trigger cleanup to avoid needing a cron job
    if secrets.randbelow(1000) == 0:
        cleanup_expired_data()
        
@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self'; "
        "media-src 'self' blob:;"
    )
    response.headers["Content-Security-Policy"] = csp
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Request payload too large."}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many requests. Please wait."}), 429

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error."}), 500

@app.errorhandler(Exception)
def handle_error(e):
    logger.error("Unhandled error", exc_info=e)
    return jsonify({"error": "Internal error"}), 500

if __name__ == "__main__":
    init_db()
    
    # Start background threads
    cleanup_thread = threading.Thread(target=cleanup_expired_data, daemon=True)
    cleanup_thread.start()
    
    email_thread = threading.Thread(target=queue_worker, daemon=True)
    email_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    debug = ENVIRONMENT == "development"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)

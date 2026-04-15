import os
import uuid
import logging
from flask import Blueprint, request, jsonify

from database import get_db
from extensions import limiter
from utils.file_utils import validate_file_upload, scan_file_content
from security.auth_middleware import require_auth, get_ip
from utils.audit_utils import audit_log

upload_bp = Blueprint("upload", __name__)
logger = logging.getLogger("SAAITA")

@upload_bp.route("/upload", methods=["POST"])
@require_auth
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
        
    # Sanitize extension: only allow alphanumeric chars and a single dot (path traversal mitigation)
    raw_ext = os.path.splitext(file.filename)[1].lower()
    safe_ext = "." + "".join(c for c in raw_ext if c.isalnum())
    if not safe_ext or safe_ext == ".":
        safe_ext = ".bin"
    stored_name = str(uuid.uuid4()) + safe_ext
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
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

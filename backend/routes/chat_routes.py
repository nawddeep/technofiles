import os
import base64
import uuid
import logging
from flask import Blueprint, request, jsonify

from database import get_db
from extensions import limiter, redis_client, REDIS_AVAILABLE
from utils.validation import has_null_bytes, MAX_JSON
from utils.file_utils import validate_file_upload, scan_file_content, MAX_FILE
from security.auth_middleware import require_auth, require_verified_email, get_ip
from utils.audit_utils import audit_log
from services.ai_service import get_gemini_model, explain_image_with_gemini, get_or_create_ai_session, GEMINI_API_KEY

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger("SAAITA")

# Keep chat objects in memory (Gemini client can't be serialized)
ai_sessions = {}

@chat_bp.route("/message", methods=["POST"])
@require_auth
@require_verified_email
@limiter.limit("100 per hour")
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
    
    ai_sess = get_or_create_ai_session(
        session_id, user["id"], user.get("onboarding_data", ""),
        ai_sessions, redis_client, REDIS_AVAILABLE, get_db
    )
    
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
                desc = explain_image_with_gemini(img_bytes, img.get("mime_type", "image/jpeg"), chat_session=ai_sess["chat"])
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

@chat_bp.route("/history", methods=["GET"])
@require_auth
def chat_history(user):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sender, text FROM chat_messages WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user["id"],)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()
        
    return jsonify({"messages": [{"sender": r["sender"], "text": r["text"]} for r in reversed(list(rows))]})

@chat_bp.route("/clear", methods=["POST"])
@require_auth
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

import os
import json
import logging
import uuid
from datetime import datetime, timezone
import google.generativeai as genai
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger("SAAITA")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_model(user_profile=""):
    try:
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_prompt.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_instruction = f.read().strip()
        else:
            base_instruction = "You are a helpful AI assistant."
            
        full_instruction = base_instruction
        if user_profile:
            full_instruction += f"\n\nUSER PROFILE: {user_profile}"
            
        return genai.GenerativeModel("gemini-2.0-flash", system_instruction=full_instruction)
    except Exception as e:
        logger.error(f"Gemini model init error: {e}")
        return None

def explain_image_with_gemini(image_bytes, mime_type="image/jpeg", chat_session=None):
    try:
        if chat_session:
            response = chat_session.send_message([
                "Describe this image in detail so another language model can understand its contents.",
                {"mime_type": mime_type, "data": image_bytes}
            ])
            return response.text
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([
            "Describe this image in detail so another language model can understand its contents.",
            {"mime_type": mime_type, "data": image_bytes}
        ])
        return response.text
    except Exception as e:
        return f"(Image processing failed: {e})"

def get_or_create_ai_session(session_id, user_id, onboarding_data, ai_sessions, redis_client, redis_available, get_db_conn):
    if session_id in ai_sessions:
        return ai_sessions[session_id]
    
    if redis_available and redis_client:
        try:
            cached = redis_client.get(f"ai_session:{session_id}")
            if cached:
                session_data = json.loads(cached)
                logger.info(f"[AI SESSION] Restored session {session_id} from Redis")
                
                conn = get_db_conn()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT sender, text FROM chat_messages WHERE user_id = %s AND chat_group_id = %s ORDER BY created_at ASC LIMIT 50",
                    (user_id, session_data["chat_group_id"])
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
                ai_sessions[session_id] = {
                    "chat": chat,
                    "chat_group_id": session_data["chat_group_id"],
                    "user_id": user_id
                }
                return ai_sessions[session_id]
        except Exception as e:
            logger.warning(f"[AI SESSION] Redis lookup failed: {e}")
            
    model = get_gemini_model(onboarding_data or "")
    if model is None:
        return None
        
    chat = model.start_chat(history=[])
    new_group_id = str(uuid.uuid4())
    
    session_data = {
        "chat_group_id": new_group_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if redis_available and redis_client:
        try:
            redis_client.setex(f"ai_session:{session_id}", 86400, json.dumps(session_data))
            logger.info(f"[AI SESSION] Stored session {session_id} to Redis")
        except Exception as e:
            logger.warning(f"[AI SESSION] Failed to store to Redis: {e}")
            
    ai_sessions[session_id] = {
        "chat": chat,
        "chat_group_id": new_group_id,
        "user_id": user_id
    }
    return ai_sessions[session_id]

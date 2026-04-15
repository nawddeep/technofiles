import json
import logging
import os
from datetime import datetime, timedelta, timezone
from database import get_db

logger = logging.getLogger("SAAITA")

# Backup log file for when DB is unreachable
AUDIT_BACKUP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit_backup.log")

def audit_log(event_type, user_id=None, ip_address=None, user_agent=None,
              resource_type=None, resource_id=None, action=None,
              details=None, session_id=None, level="INFO"):
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
        # Fallback: persist to local file so events are never lost
        try:
            backup_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "event_type": event_type,
                "user_id": user_id,
                "ip_address": ip_address,
                "details": details,
            }
            with open(AUDIT_BACKUP_FILE, "a", encoding="utf-8") as bf:
                bf.write(json.dumps(backup_entry) + "\n")
        except Exception as backup_error:
            logger.critical(f"[FATAL] Audit backup also failed: {backup_error}")
    finally:
        conn.close()

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
    """Exponential backoff brute force protection over a 24-hour window."""
    conn = get_db()
    cursor = conn.cursor()
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    if email:
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM login_attempts WHERE email = %s AND success = FALSE AND timestamp > %s",
            (email, cutoff_24h)
        )
        email_failures = cursor.fetchone()['cnt']
        if email_failures >= 20:
            conn.close()
            return True, "Account locked for 24 hours due to repeated failures. Contact support."
        elif email_failures >= 10:
            conn.close()
            return True, "Too many failed attempts. Wait 1 hour before trying again."
        elif email_failures >= 5:
            conn.close()
            return True, "Too many failed attempts. Wait 15 minutes before trying again."

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM login_attempts WHERE ip_address = %s AND success = FALSE AND timestamp > %s",
        (ip_address, cutoff_24h)
    )
    ip_count = cursor.fetchone()['cnt']
    if ip_count >= 30:
        conn.close()
        return True, "Too many failed attempts from this IP. Try again later."

    conn.close()
    return False, ""

import json
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

logger = logging.getLogger("SAAITA")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@saaita.com")

email_queue = []  # In-memory queue as fallback
email_queue_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "email_queue.json")

def queue_email(redis_client, redis_available, to_address, subject, body, retry_count=0):
    email_entry = {
        "to_address": to_address,
        "subject": subject,
        "body": body,
        "retry_count": retry_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if redis_available and redis_client:
        try:
            redis_client.lpush("email_queue", json.dumps(email_entry))
            logger.info(f"[EMAIL QUEUE] Queued email to {to_address} (Redis)")
            return
        except Exception as e:
            logger.warning(f"[EMAIL QUEUE] Failed to queue to Redis: {e}")
            
    email_queue.append(email_entry)
    logger.info(f"[EMAIL QUEUE] Queued email to {to_address} (in-memory)")
    
    try:
        with open(email_queue_file, "w") as f:
            json.dump(email_queue, f)
    except Exception as e:
        logger.warning(f"[EMAIL QUEUE] Failed to persist queue: {e}")

def load_email_queue_from_file():
    global email_queue
    if os.path.exists(email_queue_file):
        try:
            with open(email_queue_file, "r") as f:
                email_queue = json.load(f)
            logger.info(f"[EMAIL QUEUE] Recovered {len(email_queue)} queued emails from file")
        except Exception as e:
            logger.warning(f"[EMAIL QUEUE] Failed to load queue from file: {e}")

def send_email(redis_client, redis_available, to_address, subject, body):
    if not SMTP_HOST or not SMTP_USER:
        logger.info(f"[EMAIL] Would send to {to_address}: {subject}")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, to_address, msg.as_string())
        server.quit()
        logger.info(f"[EMAIL] Sent to {to_address}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"[EMAIL] Send failed: {e}. Queuing for retry.")
        queue_email(redis_client, redis_available, to_address, subject, body)
        return False

def retry_queued_emails(redis_client, redis_available):
    global email_queue
    
    if redis_available and redis_client:
        try:
            while True:
                email_json = redis_client.rpop("email_queue")
                if not email_json:
                    break
                email_entry = json.loads(email_json)
                retry_count = email_entry.get("retry_count", 0)
                
                if retry_count < 3:
                    success = send_email(redis_client, redis_available, email_entry["to_address"], email_entry["subject"], email_entry["body"])
                    if not success:
                        email_entry["retry_count"] = retry_count + 1
                        redis_client.lpush("email_queue", json.dumps(email_entry))
                else:
                    logger.error(f"[EMAIL QUEUE] Dropped email to {email_entry['to_address']} (max retries)")
        except Exception as e:
            logger.warning(f"[EMAIL QUEUE] Redis retry failed: {e}")
            
    if email_queue:
        email_queue_copy = email_queue.copy()
        email_queue.clear()
        for email_entry in email_queue_copy:
            retry_count = email_entry.get("retry_count", 0)
            if retry_count < 3:
                success = send_email(redis_client, redis_available, email_entry["to_address"], email_entry["subject"], email_entry["body"])
                if not success:
                    email_entry["retry_count"] = retry_count + 1
                    email_queue.append(email_entry)
            else:
                logger.error(f"[EMAIL QUEUE] Dropped email to {email_entry['to_address']} (max retries)")

"""
FIX 2.18: Modularized auth service
Extracted from monolithic app.py for testability and maintenance
"""
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from database import get_db

def create_user(full_name, email, password_hash):
    """Create a new user in the database"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name, email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("This email is already registered.")
    finally:
        conn.close()

def get_user_by_email(email):
    """Retrieve user by email address"""
    conn = get_db()
    cursor = conn.execute("SELECT id, full_name, email, password_hash, is_onboarded, is_verified FROM users WHERE email = ?", (email.lower(),))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    """Retrieve user by ID"""
    conn = get_db()
    cursor = conn.execute("SELECT id, full_name, email, is_onboarded, is_verified FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_onboarding(user_id, onboarding_data):
    """Mark user as onboarded with their data"""
    conn = get_db()
    cursor = conn.execute(
        "UPDATE users SET is_onboarded = 1, onboarding_data = ? WHERE id = ?",
        (onboarding_data, user_id)
    )
    conn.commit()
    conn.close()

def get_active_sessions(user_id):
    """Get all active sessions for a user"""
    conn = get_db()
    cursor = conn.execute(
        "SELECT id, session_id, created_at FROM sessions WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
        (user_id,)
    )
    sessions = cursor.fetchall()
    conn.close()
    return sessions

def revoke_session(session_id):
    """Revoke a specific session"""
    conn = get_db()
    cursor = conn.execute("UPDATE sessions SET is_active = 0 WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def revoke_all_sessions(user_id):
    """Revoke all sessions for a user (e.g., after password change)"""
    conn = get_db()
    cursor = conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

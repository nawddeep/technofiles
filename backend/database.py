"""SAAITA Database - Security Hardened Schema"""
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saaita.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_onboarded INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            onboarding_data TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Chat messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL CHECK(sender IN ('user', 'ai')),
            text TEXT NOT NULL,
            chat_group_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Refresh tokens (JWT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_jti TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            is_revoked INTEGER DEFAULT 0,
            device_info TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            user_agent TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Password reset tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Email verification tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Audit logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT DEFAULT 'INFO',
            event_type TEXT NOT NULL,
            user_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            resource_type TEXT,
            resource_id TEXT,
            action TEXT,
            details TEXT,
            session_id TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)

    # Login attempts (brute force tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            success INTEGER NOT NULL,
            user_agent TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)

    # API keys (rotation support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            name TEXT DEFAULT 'default',
            is_active INTEGER DEFAULT 1,
            last_used_at TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Security alerts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL DEFAULT 'INFO',
            alert_type TEXT NOT NULL,
            description TEXT,
            ip_address TEXT,
            user_id INTEGER,
            details TEXT,
            is_resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # File uploads
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_refresh_jti ON refresh_tokens(token_jti)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_sid ON sessions(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token)",
        "CREATE INDEX IF NOT EXISTS idx_verify_token ON email_verification_tokens(token)",
        "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_logs(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_login_email ON login_attempts(email)",
        "CREATE INDEX IF NOT EXISTS idx_login_ip ON login_attempts(ip_address)",
        "CREATE INDEX IF NOT EXISTS idx_apikeys_user ON api_keys(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON security_alerts(severity)",
    ]
    for idx in indexes:
        cursor.execute(idx)

    conn.commit()
    conn.close()
    print("[DB] Database initialized with security tables.")


def cleanup_expired_data():
    """Remove expired tokens and old data. Called periodically."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM refresh_tokens WHERE expires_at < ? AND is_revoked = 1", (now,))
    conn.execute("DELETE FROM password_reset_tokens WHERE expires_at < ?", (now,))
    conn.execute("DELETE FROM email_verification_tokens WHERE expires_at < ?", (now,))
    conn.execute("UPDATE sessions SET is_active = 0 WHERE expires_at < ?", (now,))
    cutoff = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - __import__('datetime').timedelta(days=90)).isoformat()
    conn.execute("DELETE FROM login_attempts WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM audit_logs WHERE timestamp < ? AND level = 'INFO'", (cutoff,))
    conn.commit()
    conn.close()

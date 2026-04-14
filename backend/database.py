"""SAAITA Database - PostgreSQL Security Hardened Schema"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/saaita")


def get_db():
    """Get PostgreSQL database connection with RealDictCursor for dict-like row access"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = RealDictCursor
    return conn


def init_db():
    """Initialize PostgreSQL database with all required tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_onboarded BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            onboarding_data TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Chat messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL CHECK(sender IN ('user', 'ai')),
            text TEXT NOT NULL,
            chat_group_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Refresh tokens (JWT) table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_jti TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_revoked BOOLEAN DEFAULT FALSE,
            device_info TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            user_agent TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Password reset tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Email verification tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Audit logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Login attempts (brute force tracking) table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            success BOOLEAN NOT NULL,
            user_agent TEXT DEFAULT '',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # API keys (rotation support) table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            key_hash TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            name TEXT DEFAULT 'default',
            is_active BOOLEAN DEFAULT TRUE,
            last_used_at TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Security alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_alerts (
            id SERIAL PRIMARY KEY,
            severity TEXT NOT NULL DEFAULT 'INFO',
            alert_type TEXT NOT NULL,
            description TEXT,
            ip_address TEXT,
            user_id INTEGER,
            details TEXT,
            is_resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # File uploads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_uploads (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for performance
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
    
    for idx_sql in indexes:
        cursor.execute(idx_sql)

    conn.commit()
    conn.close()
    print("[DB] PostgreSQL database initialized with security tables.")


def cleanup_expired_data():
    """Remove expired tokens and old data. Called periodically."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    
    # Delete expired and revoked refresh tokens
    cursor.execute("DELETE FROM refresh_tokens WHERE expires_at < %s AND is_revoked = TRUE", (now,))
    
    # Delete expired password reset tokens
    cursor.execute("DELETE FROM password_reset_tokens WHERE expires_at < %s", (now,))
    
    # Delete expired email verification tokens
    cursor.execute("DELETE FROM email_verification_tokens WHERE expires_at < %s", (now,))
    
    # Mark expired sessions as inactive
    cursor.execute("UPDATE sessions SET is_active = FALSE WHERE expires_at < %s", (now,))
    
    # Delete login attempts older than 90 days
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=90)
    cursor.execute("DELETE FROM login_attempts WHERE timestamp < %s", (cutoff,))
    
    # Delete old INFO-level audit logs older than 90 days
    cursor.execute("DELETE FROM audit_logs WHERE timestamp < %s AND level = 'INFO'", (cutoff,))
    
    conn.commit()
    conn.close()

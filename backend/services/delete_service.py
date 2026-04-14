"""
FIX 2.25: Soft delete service for audit compliance and data recovery
Implements soft deletes with deletion audit trail
"""
import sqlite3
import json
from datetime import datetime, timezone
from database import get_db

def soft_delete_user(user_id, deleted_by_user_id=None, reason="User requested deletion"):
    """
    FIX 2.25: Soft delete a user (mark as deleted but keep record)
    
    Args:
        user_id: ID of user to delete
        deleted_by_user_id: Admin user ID who performed deletion (optional)
        reason: Reason for deletion
    
    Returns:
        True if successful
    """
    conn = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        
        # Get user data for backup before deletion
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return False
        
        # Convert row to dict
        user_dict = dict(user_row)
        
        # Soft delete user
        conn.execute(
            "UPDATE users SET deleted_at = ? WHERE id = ?",
            (now, user_id)
        )
        
        # Log deletion in audit table
        conn.execute(
            """INSERT INTO deletion_audit 
               (table_name, record_id, user_id, deleted_by_user_id, reason, data_backup, recoverable)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            ("users", user_id, user_id, deleted_by_user_id, reason, json.dumps(user_dict))
        )
        
        # Soft delete user's data
        conn.execute(
            "UPDATE chat_messages SET deleted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        conn.execute(
            "UPDATE refresh_tokens SET deleted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        conn.execute(
            "UPDATE sessions SET deleted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def restore_user(user_id, restored_by_user_id=None):
    """
    Restore a soft-deleted user
    
    Args:
        user_id: ID of user to restore
        restored_by_user_id: ID of admin restoring user
    
    Returns:
        True if successful
    """
    conn = get_db()
    try:
        # Check if user is soft deleted
        cursor = conn.execute(
            "SELECT deleted_at FROM users WHERE id = ? AND deleted_at IS NOT NULL",
            (user_id,)
        )
        
        if not cursor.fetchone():
            return False
        
        # Restore user
        conn.execute("UPDATE users SET deleted_at = NULL WHERE id = ?", (user_id,))
        
        # Log restoration
        conn.execute(
            "UPDATE deletion_audit SET recoverable = 0 WHERE table_name = 'users' AND record_id = ? AND recoverable = 1",
            (user_id,)
        )
        
        conn.commit()
        return True
    finally:
        conn.close()

def hard_delete_old_data(days_since_soft_delete=90):
    """
    Permanently delete soft-deleted data older than X days
    (GDPR "right to be forgotten" compliance)
    
    Args:
        days_since_soft_delete: Delete records soft-deleted more than X days ago
    
    Returns:
        Number of records permanently deleted
    """
    conn = get_db()
    try:
        # Calculate cutoff date
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(day=cutoff.day - days_since_soft_delete)
        cutoff_str = cutoff.isoformat()
        
        # Delete old soft-deleted messages
        cursor = conn.execute(
            "DELETE FROM chat_messages WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (cutoff_str,)
        )
        deleted_count = cursor.rowcount
        
        # Delete old soft-deleted tokens
        cursor = conn.execute(
            "DELETE FROM refresh_tokens WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (cutoff_str,)
        )
        deleted_count += cursor.rowcount
        
        # Delete old soft-deleted sessions
        cursor = conn.execute(
            "DELETE FROM sessions WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (cutoff_str,)
        )
        deleted_count += cursor.rowcount
        
        conn.commit()
        return deleted_count
    finally:
        conn.close()

def get_deletion_audit(table_name=None, user_id=None, days_back=30):
    """
    Query deletion audit trail for compliance/recovery purposes
    
    Args:
        table_name: Filter by table name (optional)
        user_id: Filter by user who was deleted (optional)
        days_back: Only show deletions in last N days
    
    Returns:
        List of deletion audit records
    """
    conn = get_db()
    try:
        query = "SELECT * FROM deletion_audit WHERE 1=1"
        params = []
        
        if table_name:
            query += " AND table_name = ?"
            params.append(table_name)
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        # Filter by date
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(day=cutoff.day - days_back)
        cutoff_str = cutoff.isoformat()
        query += " AND deleted_at > ?"
        params.append(cutoff_str)
        
        query += " ORDER BY deleted_at DESC"
        
        cursor = conn.execute(query, params)
        records = cursor.fetchall()
        
        return records
    finally:
        conn.close()

def is_user_deleted(user_id):
    """Check if user is soft-deleted"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT deleted_at FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return row and row[0] is not None
    finally:
        conn.close()

# Helper: When querying users, always filter out soft-deleted by default
def get_active_users_query():
    """Returns SQL WHERE clause for excluding deleted users"""
    return "users.deleted_at IS NULL"

def get_active_messages_query():
    """Returns SQL WHERE clause for excluding deleted messages"""
    return "chat_messages.deleted_at IS NULL"

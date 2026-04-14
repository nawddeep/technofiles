"""
FIX 2.25: Soft delete service for audit compliance and data recovery
Implements soft deletes with deletion audit trail
"""
import psycopg2
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
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        # Get user data for backup before deletion
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            return False
        
        # Convert row to dict (RealDictCursor already returns dict-like objects)
        user_dict = dict(user_row)
        
        # Soft delete user
        cursor.execute(
            "UPDATE users SET deleted_at = %s WHERE id = %s",
            (now, user_id)
        )
        
        # Log deletion in audit table
        cursor.execute(
            """INSERT INTO deletion_audit 
               (table_name, record_id, user_id, deleted_by_user_id, reason, data_backup, recoverable)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE)""",
            ("users", user_id, user_id, deleted_by_user_id, reason, json.dumps(user_dict))
        )
        
        # Soft delete user's data
        cursor.execute(
            "UPDATE chat_messages SET deleted_at = %s WHERE user_id = %s",
            (now, user_id)
        )
        cursor.execute(
            "UPDATE refresh_tokens SET deleted_at = %s WHERE user_id = %s",
            (now, user_id)
        )
        cursor.execute(
            "UPDATE sessions SET deleted_at = %s WHERE user_id = %s",
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
        cursor = conn.cursor()
        # Check if user is soft deleted
        cursor.execute(
            "SELECT deleted_at FROM users WHERE id = %s AND deleted_at IS NOT NULL",
            (user_id,)
        )
        
        if not cursor.fetchone():
            return False
        
        # Restore user
        cursor.execute("UPDATE users SET deleted_at = NULL WHERE id = %s", (user_id,))
        
        # Log restoration
        cursor.execute(
            "UPDATE deletion_audit SET recoverable = FALSE WHERE table_name = %s AND record_id = %s AND recoverable = TRUE",
            ('users', user_id)
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
        cursor = conn.cursor()
        # Calculate cutoff date
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(day=cutoff.day - days_since_soft_delete)
        cutoff_str = cutoff.isoformat()
        
        # Delete old soft-deleted messages
        cursor.execute(
            "DELETE FROM chat_messages WHERE deleted_at IS NOT NULL AND deleted_at < %s",
            (cutoff_str,)
        )
        deleted_count = cursor.rowcount
        
        # Delete old soft-deleted tokens
        cursor.execute(
            "DELETE FROM refresh_tokens WHERE deleted_at IS NOT NULL AND deleted_at < %s",
            (cutoff_str,)
        )
        deleted_count += cursor.rowcount
        
        # Delete old soft-deleted sessions
        cursor.execute(
            "DELETE FROM sessions WHERE deleted_at IS NOT NULL AND deleted_at < %s",
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
        cursor = conn.cursor()
        query = "SELECT * FROM deletion_audit WHERE 1=1"
        params = []
        
        if table_name:
            query += " AND table_name = %s"
            params.append(table_name)
        
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        
        # Filter by date
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(day=cutoff.day - days_back)
        cutoff_str = cutoff.isoformat()
        query += " AND deleted_at > %s"
        params.append(cutoff_str)
        
        query += " ORDER BY deleted_at DESC"
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        return records
    finally:
        conn.close()

def is_user_deleted(user_id):
    """Check if user is soft-deleted"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT deleted_at FROM users WHERE id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        return row and row['deleted_at'] is not None
    finally:
        conn.close()

# Helper: When querying users, always filter out soft-deleted by default
def get_active_users_query():
    """Returns SQL WHERE clause for excluding deleted users"""
    return "users.deleted_at IS NULL"

def get_active_messages_query():
    """Returns SQL WHERE clause for excluding deleted messages"""
    return "chat_messages.deleted_at IS NULL"

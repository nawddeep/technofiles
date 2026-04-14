"""
FIX 2.18: Modularized chat service
FIX 2.24: Added pagination support for chat history
Extracted from monolithic app.py for testability and maintenance
"""
import sqlite3
from database import get_db
import base64

def save_message(user_id, sender, text, chat_group_id=None):
    """Save a chat message to database"""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO chat_messages (user_id, sender, text, chat_group_id) VALUES (?, ?, ?, ?)",
        (user_id, sender, text, chat_group_id)
    )
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def get_chat_history(user_id, chat_group_id=None, limit=50, offset=0):
    """
    FIX 2.24: Get paginated chat history for a user (offset-based pagination)
    
    Args:
        user_id: User ID
        chat_group_id: Optional session ID to filter
        limit: Messages per page (default 50, max 100)
        offset: Number of messages to skip
    
    Returns:
        List of messages in chronological order with pagination info
    """
    limit = min(int(limit), 100)  # Cap at 100 to prevent abuse
    offset = max(int(offset), 0)
    
    conn = get_db()
    query = "SELECT id, sender, text, created_at FROM chat_messages WHERE user_id = ?"
    params = [user_id]
    
    if chat_group_id:
        query += " AND chat_group_id = ?"
        params.append(chat_group_id)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = conn.execute(query, params)
    messages = cursor.fetchall()
    conn.close()
    
    # Reverse to get chronological order
    return list(reversed(messages))

def get_chat_history_cursor(user_id, chat_group_id=None, limit=50, cursor_token=None):
    """
    FIX 2.24: Get paginated chat with cursor-based pagination (better for large datasets)
    
    Args:
        user_id: User ID
        chat_group_id: Optional session ID
        limit: Messages per page
        cursor_token: Base64 encoded cursor (message ID from previous response)
    
    Returns:
        Dict with messages, next_cursor, and has_more flag
    """
    limit = min(int(limit), 100)
    
    # Decode cursor if provided
    last_message_id = None
    if cursor_token:
        try:
            last_message_id = int(base64.b64decode(cursor_token).decode())
        except:
            last_message_id = None
    
    conn = get_db()
    query = "SELECT id, sender, text, created_at FROM chat_messages WHERE user_id = ?"
    params = [user_id]
    
    if chat_group_id:
        query += " AND chat_group_id = ?"
        params.append(chat_group_id)
    
    # If cursor provided, only get messages after it
    if last_message_id:
        query += " AND id > ?"
        params.append(last_message_id)
    
    query += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit + 1)  # Get one extra to determine if more exist
    
    cursor = conn.execute(query, params)
    messages = list(cursor.fetchall())
    conn.close()
    
    # Check if more messages exist
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]
    
    # Generate next cursor
    next_cursor = None
    if messages and has_more:
        last_id = messages[-1][0]
        next_cursor = base64.b64encode(str(last_id).encode()).decode()
    
    return {
        "messages": messages,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "limit": limit
    }

def clear_chat(user_id, chat_group_id):
    """Delete all messages in a chat group"""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM chat_messages WHERE user_id = ? AND chat_group_id = ?",
        (user_id, chat_group_id)
    )
    conn.commit()
    conn.close()

def get_message_count(user_id, chat_group_id=None):
    """Get total message count for pagination"""
    conn = get_db()
    query = "SELECT COUNT(*) FROM chat_messages WHERE user_id = ?"
    params = [user_id]
    
    if chat_group_id:
        query += " AND chat_group_id = ?"
        params.append(chat_group_id)
    
    cursor = conn.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

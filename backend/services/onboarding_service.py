"""
FIX 2.23: Onboarding service with JSON schema validation
Handles flexible onboarding data storage with validation
"""
import json
import sqlite3
from database import get_db

# Schema for onboarding data - defines valid structure
ONBOARDING_SCHEMA = {
    "type": "object",
    "properties": {
        "learning_goals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "User's learning objectives"
        },
        "preferred_topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topics of interest"
        },
        "skill_level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced"],
            "description": "Current skill level"
        },
        "preferred_language": {
            "type": "string",
            "enum": ["en", "es", "fr", "de", "ja", "zh"],
            "description": "Preferred language for content"
        },
        "availability_hours": {
            "type": "integer",
            "minimum": 1,
            "maximum": 40,
            "description": "Hours per week available for learning"
        }
    },
    "required": ["learning_goals", "skill_level"]
}

def validate_onboarding_data(data):
    """Validate onboarding data against schema"""
    if not isinstance(data, dict):
        return False, "Onboarding data must be a JSON object"
    
    # Check required fields
    if "learning_goals" not in data:
        return False, "learning_goals is required"
    if "skill_level" not in data:
        return False, "skill_level is required"
    
    # Check skill_level is valid
    if data["skill_level"] not in ["beginner", "intermediate", "advanced"]:
        return False, "skill_level must be one of: beginner, intermediate, advanced"
    
    # Check learning_goals is array
    if not isinstance(data.get("learning_goals"), list):
        return False, "learning_goals must be an array"
    
    return True, None

def save_onboarding(user_id, onboarding_data):
    """Save onboarding data for user with validation"""
    ok, err = validate_onboarding_data(onboarding_data)
    if not ok:
        raise ValueError(f"Invalid onboarding data: {err}")
    
    conn = get_db()
    try:
        data_json = json.dumps(onboarding_data)
        cursor = conn.execute(
            """INSERT INTO onboarding_data (user_id, learning_goals, preferred_topics, skill_level, preferred_language)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                json.dumps(onboarding_data.get("learning_goals", [])),
                json.dumps(onboarding_data.get("preferred_topics", [])),
                onboarding_data.get("skill_level", "beginner"),
                onboarding_data.get("preferred_language", "en")
            )
        )
        
        # Also update users table for backward compatibility
        conn.execute(
            "UPDATE users SET is_onboarded = 1, onboarding_data = ? WHERE id = ?",
            (data_json, user_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_onboarding(user_id):
    """Retrieve onboarding data for user"""
    conn = get_db()
    try:
        # Try new table first
        cursor = conn.execute(
            """SELECT learning_goals, preferred_topics, skill_level, preferred_language
               FROM onboarding_data WHERE user_id = ?""",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "learning_goals": json.loads(row[0]) if row[0] else [],
                "preferred_topics": json.loads(row[1]) if row[1] else [],
                "skill_level": row[2],
                "preferred_language": row[3]
            }
        
        # Fallback to old users table
        cursor = conn.execute(
            "SELECT onboarding_data FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row and row[0]:
            return json.loads(row[0])
        
        return None
    finally:
        conn.close()

def get_users_by_skill_level(skill_level):
    """Find users by skill level - useful for cohort-based learning"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT user_id FROM onboarding_data WHERE skill_level = ?",
            (skill_level,)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_users_interested_in_topic(topic):
    """Find users interested in a specific topic"""
    conn = get_db()
    try:
        # For SQLite, use LIKE with JSON array search
        # For PostgreSQL, use @> JSONB operator
        cursor = conn.execute(
            """SELECT user_id FROM onboarding_data 
               WHERE preferred_topics LIKE ?""",
            (f'%{topic}%',)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

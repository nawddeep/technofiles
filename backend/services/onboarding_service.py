"""
FIX 2.23: Onboarding service with JSON schema validation
Handles flexible onboarding data storage with validation
"""
import json
import psycopg2
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
        cursor = conn.cursor()
        data_json = json.dumps(onboarding_data)
        cursor.execute(
            """INSERT INTO onboarding_data (user_id, learning_goals, preferred_topics, skill_level, preferred_language)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                user_id,
                json.dumps(onboarding_data.get("learning_goals", [])),
                json.dumps(onboarding_data.get("preferred_topics", [])),
                onboarding_data.get("skill_level", "beginner"),
                onboarding_data.get("preferred_language", "en")
            )
        )
        
        # Also update users table for backward compatibility
        cursor.execute(
            "UPDATE users SET is_onboarded = TRUE, onboarding_data = %s WHERE id = %s",
            (data_json, user_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_onboarding(user_id):
    """Retrieve onboarding data for user"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Try new table first
        cursor.execute(
            """SELECT learning_goals, preferred_topics, skill_level, preferred_language
               FROM onboarding_data WHERE user_id = %s""",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "learning_goals": json.loads(row['learning_goals']) if row['learning_goals'] else [],
                "preferred_topics": json.loads(row['preferred_topics']) if row['preferred_topics'] else [],
                "skill_level": row['skill_level'],
                "preferred_language": row['preferred_language']
            }
        
        # Fallback to old users table
        cursor.execute(
            "SELECT onboarding_data FROM users WHERE id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row and row['onboarding_data']:
            return json.loads(row['onboarding_data'])
        
        return None
    finally:
        conn.close()

def get_users_by_skill_level(skill_level):
    """Find users by skill level - useful for cohort-based learning"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM onboarding_data WHERE skill_level = %s",
            (skill_level,)
        )
        return [row['user_id'] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_users_interested_in_topic(topic):
    """Find users interested in a specific topic"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        # For PostgreSQL, use ILIKE for case-insensitive search in JSON text
        cursor.execute(
            """SELECT user_id FROM onboarding_data 
               WHERE preferred_topics::text ILIKE %s""",
            (f'%{topic}%',)
        )
        return [row['user_id'] for row in cursor.fetchall()]
    finally:
        conn.close()

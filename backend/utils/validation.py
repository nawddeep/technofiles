import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MAX_JSON = 5 * 1024 * 1024  # 5MB
MAX_FILE = 5 * 1024 * 1024  # 5MB

def has_null_bytes(data):
    if isinstance(data, str):
        return "\x00" in data
    if isinstance(data, dict):
        return any(has_null_bytes(v) for v in data.values())
    if isinstance(data, list):
        return any(has_null_bytes(v) for v in data)
    return False

def validate_email(email):
    if not email or len(email) > 255:
        return False, "Invalid email address."
    if not EMAIL_RE.match(email):
        return False, "Invalid email format."
    return True, ""

def validate_password(password):
    if not password:
        return False, "Password is required."
    if len(password) < 12:
        return False, "Password must be at least 12 characters long."
    if len(password) > 128:
        return False, "Password is too long."
    return True, ""

def validate_schema(data, schema_type):
    if not isinstance(data, dict):
        return False, "Invalid JSON data."
    
    if schema_type == "signup":
        required = ["fullName", "email", "password"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: {field}"
        return True, ""
        
    elif schema_type == "login":
        required = ["email", "password"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: {field}"
        return True, ""
        
    elif schema_type == "change_password":
        required = ["current_password", "new_password"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: {field}"
        return True, ""
        
    elif schema_type == "password_reset_request":
        required = ["email"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: {field}"
        return True, ""
        
    elif schema_type == "password_reset":
        required = ["token", "new_password"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: {field}"
        return True, ""
        
    return False, "Unknown schema type."

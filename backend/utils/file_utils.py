import os

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", "doc", "docx"}
MAX_FILE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_upload(file):
    if not file or not file.filename:
        return False, "No file selected."
    if not allowed_file(file.filename):
        return False, "File type not allowed."
    return True, ""

def scan_file_content(file_bytes):
    if len(file_bytes) > MAX_FILE:
        return False, "File is too large."
        
    try:
        try:
            content_str = file_bytes.decode("utf-8")
            bad_patterns = ["<script", "javascript:", "onload=", "onerror=", "<?php", "exec(", "eval("]
            lower_content = content_str.lower()
            if any(p in lower_content for p in bad_patterns):
                return False, "Suspicious content detected."
        except UnicodeDecodeError:
            pass
            
        header = file_bytes[:8]
        if b"<?php" in header or b"MZ" in header:
            return False, "Suspicious file header detected."
            
        return True, ""
    except Exception as e:
        import logging
        logging.getLogger("SAAITA").warning(f"File scan failed: {e}")
        return False, "File could not be scanned."

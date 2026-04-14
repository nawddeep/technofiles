# SAAITA Project Issues & TODO

## 🚨 CRITICAL ISSUES (Fix First)

### 1. Monolithic Backend
- **Issue:** 1454-line app.py file - unmaintainable
- **Fix:** Split into modules: routes/, services/, middleware/
- **Priority:** HIGH

### 2. No Tests
- **Issue:** Only 2 test files, no coverage
- **Fix:** Add pytest tests for all endpoints, aim 70%+ coverage
- **Priority:** HIGH

### 3. Hardcoded Secrets
- **Issue:** JWT_SECRET_KEY defaults to empty string
- **Fix:** Add startup validation for required env vars
- **Priority:** HIGH

### 4. Fake Redis Fallback
- **Issue:** In-memory fallback breaks in production
- **Fix:** Make Redis required, remove fallbacks
- **Priority:** HIGH

### 5. Broken Email Queue
- **Issue:** In-memory queue lost on restart, random retry
- **Fix:** Use Celery + Redis for background tasks
- **Priority:** MEDIUM

## ⚠️ ARCHITECTURE ISSUES

### 6. No Database Migrations
- **Issue:** Manual SQL scripts, no version control
- **Fix:** Use Alembic for proper migrations
- **Priority:** MEDIUM

### 7. No State Management (Frontend)
- **Issue:** Prop drilling, useState hell
- **Fix:** Add Zustand or React Context
- **Priority:** MEDIUM

### 8. No Error Boundaries
- **Issue:** Poor error handling, no user feedback
- **Fix:** Add Sentry, proper error boundaries
- **Priority:** MEDIUM

### 9. Chat Rate Limiting Too Strict
- **Issue:** 20 messages/hour = 1 every 3 minutes
- **Fix:** Increase to 100/hour or remove
- **Priority:** LOW

### 10. No WebSockets
- **Issue:** Polling for chat responses
- **Fix:** Add WebSocket or SSE for real-time chat
- **Priority:** MEDIUM

## 🔧 CODE QUALITY ISSUES

### 11. Image Processing Security
- **Issue:** Size check after base64 decode
- **Fix:** Check base64 string length first
- **Priority:** MEDIUM

### 12. Unbounded Chat History
- **Issue:** Always loads 50 messages
- **Fix:** Add proper pagination
- **Priority:** LOW

### 13. JSON as TEXT in DB
- **Issue:** onboarding_data stored as TEXT
- **Fix:** Use PostgreSQL JSONB column
- **Priority:** LOW

### 14. No Logging Strategy
- **Issue:** Random print() and logger calls
- **Fix:** Use structlog for consistent logging
- **Priority:** LOW

### 15. Inconsistent API Error Handling
- **Issue:** Some endpoints catch errors, some don't
- **Fix:** Add global error handler middleware
- **Priority:** MEDIUM

## 📱 FRONTEND ISSUES

### 16. No TypeScript
- **Issue:** JavaScript in 2026
- **Fix:** Migrate to TypeScript
- **Priority:** LOW

### 17. No Mobile Optimization
- **Issue:** UI breaks on mobile
- **Fix:** Test and fix responsive design
- **Priority:** MEDIUM

### 18. Browser-Only Voice Input
- **Issue:** Only works in Chrome/Edge
- **Fix:** Add fallback or remove feature
- **Priority:** LOW

### 19. No Dark Mode
- **Issue:** Only light theme
- **Fix:** Add dark/light mode toggle
- **Priority:** LOW

### 20. No Accessibility
- **Issue:** No ARIA labels, keyboard nav
- **Fix:** Add proper a11y support
- **Priority:** MEDIUM

## 🚀 PRODUCTION READINESS

### 21. No CI/CD Pipeline
- **Issue:** No automated testing/deployment
- **Fix:** Add GitHub Actions
- **Priority:** MEDIUM

### 22. No Monitoring
- **Issue:** No health checks, metrics
- **Fix:** Add Sentry, health endpoints
- **Priority:** MEDIUM

### 23. No Backup Strategy
- **Issue:** No database backups
- **Fix:** Set up automated PostgreSQL backups
- **Priority:** HIGH

### 24. Weak CSP Headers
- **Issue:** Too permissive Content Security Policy
- **Fix:** Tighten CSP rules
- **Priority:** LOW

### 25. No Load Testing
- **Issue:** Unknown performance limits
- **Fix:** Add load testing with k6 or Artillery
- **Priority:** MEDIUM

## 📊 QUICK WINS

### 26. Add Environment Validation
```python
required_vars = ["DATABASE_URL", "JWT_SECRET_KEY", "GEMINI_API_KEY"]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    raise SystemExit(f"Missing: {missing}")
```

### 27. Fix Image Size Check
```python
if len(img["data"]) > MAX_FILE * 1.5:  # Check before decode
    continue
```

### 28. Add Global Error Handler
```python
@app.errorhandler(Exception)
def handle_error(e):
    logger.error("Unhandled error", exc_info=e)
    return jsonify({"error": "Internal error"}), 500
```

### 29. Increase Chat Rate Limit
```python
@limiter.limit("100 per hour")  # Was 20
```

### 30. Add Health Check
```python
@app.route("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}
```

---

## PRIORITY ORDER
1. **HIGH:** Issues 1, 2, 3, 4, 23
2. **MEDIUM:** Issues 5, 6, 7, 8, 10, 11, 15, 17, 20, 21, 22, 25
3. **LOW:** Everything else

**Estimated Time:** 2-3 weeks for HIGH priority items
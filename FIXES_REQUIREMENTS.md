# SAAITA Critical Fixes - Requirements Document

**Version:** 1.0  
**Date:** 2026-04-14  
**Status:** Draft  
**Priority:** HIGH

---

## Executive Summary

This document outlines critical fixes needed to transform SAAITA from an over-engineered prototype into a production-ready student AI assistant. The current implementation has 15 major issues that prevent deployment, scalability, and maintainability.

**Estimated Effort:** 40-60 hours  
**Risk Level:** Medium (breaking changes required)  
**Target Completion:** 2 weeks

---

## Problem Categories

1. **Infrastructure & Dependencies** (Critical)
2. **Security & Authentication** (High)
3. **AI Session Management** (Critical)
4. **Data Storage & Scalability** (High)
5. **User Experience** (Medium)
6. **Testing & Quality** (High)

---

## Detailed Requirements

### 1. Database Migration Strategy

**Problem:** Mixed SQLite/PostgreSQL implementation, no clear production path.

**Requirements:**

#### 1.1 Database Abstraction Layer
- Create `database_factory.py` that returns appropriate DB connection based on environment
- Support SQLite for development, PostgreSQL for production
- Use environment variable `DATABASE_TYPE` (sqlite|postgresql)

**Acceptance Criteria:**
- Single codebase works with both databases
- No code changes needed to switch databases
- Migration scripts work for both DB types

#### 1.2 Connection Pooling
- Implement connection pooling for PostgreSQL using `psycopg2.pool`
- Add connection timeout and retry logic
- Graceful handling of connection failures

**Acceptance Criteria:**
- Max 20 connections in pool
- 30-second connection timeout
- Automatic retry on transient failures (max 3 attempts)

---

### 2. Email Service Graceful Degradation

**Problem:** Signup blocked if SMTP not configured, poor error handling.

**Requirements:**

#### 2.1 Optional Email Verification
- Allow signup without email verification
- Mark users as `is_verified=False` by default
- Send verification email asynchronously (background task)
- Allow users to resend verification email from dashboard

**Acceptance Criteria:**
- Users can sign up even if SMTP fails
- Verification email sent in background (Celery/RQ or simple threading)
- Users can access basic features without verification
- Premium features require verification (configurable)

#### 2.2 Email Service Fallback
- If SMTP fails, log error but don't crash
- Store unsent emails in `pending_emails` table
- Retry failed emails every 5 minutes (background job)
- Admin dashboard to view failed emails

**Acceptance Criteria:**
- App never returns 503 due to email failure
- Failed emails stored in database
- Retry mechanism with exponential backoff
- Admin can manually trigger email resend

---

### 3. Redis Graceful Degradation

**Problem:** App crashes if Redis unavailable, no fallback.

**Requirements:**

#### 3.1 Optional Redis Dependency
- Make Redis optional for development
- Fall back to in-memory storage if Redis unavailable
- Use environment variable `REDIS_ENABLED` (true|false)

**Acceptance Criteria:**
- App starts without Redis in development mode
- Warning logged if Redis unavailable
- In-memory fallback for: rate limiting, CSRF tokens, AI sessions
- Production mode requires Redis (fail fast with clear error)

#### 3.2 Redis Connection Resilience
- Implement connection retry logic (max 3 attempts)
- Circuit breaker pattern for Redis operations
- Graceful degradation: if Redis fails, disable rate limiting temporarily

**Acceptance Criteria:**
- Redis connection retries with exponential backoff
- Circuit breaker opens after 5 consecutive failures
- Rate limiting disabled (with warning) if Redis unavailable
- Health check endpoint reports Redis status

---

### 4. AI Session Management Refactor

**Problem:** Sessions stored in both Redis and memory, lost on restart.

**Requirements:**

#### 4.1 Database-Backed Sessions
- Remove in-memory `ai_sessions` dict
- Store only session metadata in Redis (user_id, chat_group_id, last_active)
- Reconstruct Gemini chat from database on each request
- Cache last 10 messages in Redis for performance

**Acceptance Criteria:**
- No in-memory session storage
- Sessions survive server restart
- Chat history loaded from database
- Redis caches recent messages (10 messages, 1-hour TTL)

#### 4.2 Chat History Pagination
- Limit chat history to last 50 messages for Gemini context
- Implement cursor-based pagination for frontend
- Add `GET /api/v1/chat/history?limit=50&cursor=<id>` endpoint

**Acceptance Criteria:**
- Gemini receives max 50 messages as context
- Frontend can load older messages on scroll
- Database query uses indexed `created_at` column
- Response includes `next_cursor` for pagination

#### 4.3 Session Cleanup
- Expire inactive sessions after 24 hours
- Background job to clean up old sessions (daily)
- Archive old chat messages (>90 days) to separate table

**Acceptance Criteria:**
- Redis sessions expire after 24 hours of inactivity
- Daily cleanup job removes expired sessions
- Old messages moved to `chat_messages_archive` table

---

### 5. File Upload Security Fix

**Problem:** Broken malicious content detection, undefined variable crash.

**Requirements:**

#### 5.1 Remove Security Theater
- Remove JavaScript pattern matching from image files
- Keep only: MIME type validation, file size check, extension validation
- Use `python-magic` for accurate MIME type detection

**Acceptance Criteria:**
- No regex scanning of binary files
- MIME type verified using libmagic
- Max file size: 5MB (configurable)
- Allowed types: JPEG, PNG, GIF, WebP

#### 5.2 Image Processing
- Resize images to max 1920x1080 before storage
- Convert all images to JPEG (quality 85%)
- Strip EXIF metadata for privacy
- Use Pillow library for processing

**Acceptance Criteria:**
- Images resized on upload
- EXIF data removed
- Storage optimized (smaller files)
- Original filename preserved in metadata

---

### 6. API Versioning Cleanup

**Problem:** Duplicate routes, broken decorator, no actual versioning strategy.

**Requirements:**

#### 6.1 Single Version Strategy
- Remove `/api` legacy routes
- Use only `/api/v1` endpoints
- Update frontend to use `/api/v1`
- Add deprecation notice in API docs

**Acceptance Criteria:**
- All routes use `/api/v1` prefix
- Frontend updated to new endpoints
- Old `/api` routes return 410 Gone with migration instructions
- API documentation updated

#### 6.2 Version Header Support
- Accept `API-Version: 1` header
- Default to v1 if header missing
- Prepare for v2 (future-proofing)

**Acceptance Criteria:**
- Routes check `API-Version` header
- Invalid version returns 400 with supported versions
- Version logged in audit logs

---

### 7. Rate Limiting for Chat

**Problem:** No rate limiting on chat endpoint, API cost explosion risk.

**Requirements:**

#### 7.1 Chat Rate Limits
- Implement rate limiting: 20 messages per hour per user
- Separate limits for free vs verified users
- Return 429 with `Retry-After` header

**Acceptance Criteria:**
- Free users: 20 messages/hour
- Verified users: 50 messages/hour
- Rate limit stored in Redis (or in-memory fallback)
- Clear error message with retry time

#### 7.2 Token Usage Tracking
- Track Gemini API token usage per user
- Store in `api_usage` table (user_id, tokens_used, date)
- Daily usage limits: 100k tokens per user
- Admin dashboard for usage monitoring

**Acceptance Criteria:**
- Token usage logged per request
- Daily limit enforced
- Usage visible in user dashboard
- Admin can view top users by token usage

---

### 8. Environment Configuration Overhaul

**Problem:** Too many required env vars, crashes on missing config.

**Requirements:**

#### 8.1 Configuration Validation
- Create `config.py` with validation logic
- Provide sensible defaults for development
- Clear error messages for missing required vars
- Separate dev/staging/prod configs

**Acceptance Criteria:**
- Single source of truth for config
- Development works with minimal config
- Production validates all required vars on startup
- Config validation errors are human-readable

#### 8.2 Required vs Optional Variables
**Required (Production):**
- `JWT_SECRET_KEY` (min 32 chars)
- `DATABASE_URL` (PostgreSQL connection string)
- `ALLOWED_ORIGINS` (comma-separated)
- `GEMINI_API_KEY`

**Optional (with defaults):**
- `REDIS_URL` (default: disabled)
- `SMTP_*` (default: log emails to console)
- `ENVIRONMENT` (default: development)
- `RATE_LIMIT_ENABLED` (default: true in production)

**Acceptance Criteria:**
- App starts with only required vars in production
- Development works with zero config (uses defaults)
- `.env.example` clearly documents all variables
- Startup logs show which optional features are disabled

---

### 9. Learning Path Structured Outputs

**Problem:** Fragile JSON parsing, no fallback, non-deterministic AI responses.

**Requirements:**

#### 9.1 Gemini Function Calling
- Use Gemini's function calling API for structured outputs
- Define schema for learning paths and checklists
- Validate responses before sending to frontend
- Fallback to plain text if parsing fails

**Acceptance Criteria:**
- Learning paths use function calling schema
- Invalid responses handled gracefully
- Frontend receives validated JSON or plain text
- No regex parsing of AI responses

#### 9.2 Response Validation
- Use Pydantic models for response validation
- Sanitize AI-generated content (XSS prevention)
- Log validation failures for debugging
- Return user-friendly error if AI response invalid

**Acceptance Criteria:**
- All structured responses validated with Pydantic
- XSS-safe content rendering
- Validation errors logged with request ID
- User sees "AI response format error" message

---

### 10. Onboarding Data Structure

**Problem:** Storing structured data as plain text string.

**Requirements:**

#### 10.1 JSON Storage
- Change `onboarding_data` column to JSONB (PostgreSQL) or JSON (SQLite)
- Store structured data: `{"journey": "ug", "goal": "finance", ...}`
- Validate schema on save
- Migrate existing data

**Acceptance Criteria:**
- Onboarding data stored as JSON
- Schema validation on save
- Easy to query specific fields
- Migration script for existing users

#### 10.2 Profile API
- Add `GET /api/v1/user/profile` endpoint
- Add `PATCH /api/v1/user/profile` to update preferences
- Return structured profile data
- Allow partial updates

**Acceptance Criteria:**
- Profile endpoint returns JSON
- Users can update individual fields
- Changes reflected in AI responses
- Audit log tracks profile changes

---

### 11. CORS and Cookie Configuration

**Problem:** Conflicting CORS and SameSite settings.

**Requirements:**

#### 11.1 Cookie Strategy
- Use `SameSite=Lax` for CSRF token (readable by JS)
- Use `SameSite=Strict` for auth tokens (httpOnly)
- Set `Secure=True` only in production (HTTPS)
- Remove `supports_credentials` from CORS in development

**Acceptance Criteria:**
- Cookies work in development (localhost)
- Cookies secure in production (HTTPS only)
- CSRF protection functional
- No browser console warnings

---

### 12. Testing Infrastructure

**Problem:** No tests, pytest installed but unused.

**Requirements:**

#### 12.1 Unit Tests
- Test coverage for: auth, chat, onboarding, validation
- Use pytest fixtures for database setup
- Mock external services (Gemini, SMTP, Redis)
- Target: 70% code coverage

**Acceptance Criteria:**
- 50+ unit tests
- All tests pass
- Coverage report generated
- CI/CD integration ready

#### 12.2 Integration Tests
- Test full user flows: signup → onboarding → chat
- Test error scenarios: DB failure, API timeout, invalid input
- Use test database (SQLite in-memory)

**Acceptance Criteria:**
- 10+ integration tests
- Tests run in isolated environment
- Database reset between tests
- Tests complete in <30 seconds

#### 12.3 API Tests
- Test all endpoints with various inputs
- Test rate limiting
- Test authentication flows
- Use `pytest-flask` or `httpx`

**Acceptance Criteria:**
- All endpoints tested
- Auth flows validated
- Rate limiting verified
- Response schemas validated

---

### 13. Frontend Simplification

**Problem:** Overengineered UI, confusing UX, unused features.

**Requirements:**

#### 13.1 Remove Dashboard Home
- Remove `DashboardHome` component
- Default view: Chat
- Navbar: Chat | Learning Paths | Profile | Logout

**Acceptance Criteria:**
- Dashboard loads directly to chat
- 3-tab navigation (Chat, Paths, Profile)
- No empty placeholder screens

#### 13.2 Learning Paths View
- Show saved learning paths (from chat history)
- Allow users to mark steps as complete
- Progress tracking per path
- Export path as PDF

**Acceptance Criteria:**
- Paths extracted from chat history
- Progress saved in database
- Visual progress indicators
- PDF export functional

#### 13.3 Profile View
- Show user info and onboarding preferences
- Allow editing preferences
- Show API usage stats
- Email verification status

**Acceptance Criteria:**
- Profile editable
- Changes saved to backend
- Usage stats displayed
- Verification email resend button

---

### 14. Audit Log Resilience

**Problem:** App crashes if audit log fails.

**Requirements:**

#### 14.1 Non-Blocking Audit Logs
- Remove `raise SystemExit` from audit_log function
- Log errors but continue execution
- Queue failed audit logs for retry
- Alert admin on repeated failures

**Acceptance Criteria:**
- Audit log failures don't crash app
- Failed logs queued in `pending_audit_logs` table
- Background job retries failed logs
- Admin alert after 10 consecutive failures

---

### 15. Soft Deletes Implementation

**Problem:** Migration exists but not implemented.

**Requirements:**

#### 15.1 Soft Delete Support
- Add `deleted_at` column to: users, chat_messages, sessions
- Update queries to filter `deleted_at IS NULL`
- Add `DELETE /api/v1/user/account` endpoint (soft delete)
- Background job to hard delete after 30 days

**Acceptance Criteria:**
- Soft delete implemented for key tables
- Deleted users can't log in
- Data retained for 30 days
- Hard delete job runs daily

---

## Implementation Priority

### Phase 1: Critical Fixes (Week 1)
1. Database abstraction layer
2. Redis graceful degradation
3. Email service fallback
4. AI session management refactor
5. File upload security fix

### Phase 2: Scalability (Week 2)
6. Chat history pagination
7. Rate limiting for chat
8. Environment configuration overhaul
9. CORS and cookie fixes

### Phase 3: Quality & UX (Week 3)
10. Testing infrastructure
11. Learning path structured outputs
12. Onboarding data structure
13. Frontend simplification

### Phase 4: Polish (Week 4)
14. Audit log resilience
15. Soft deletes implementation
16. API versioning cleanup
17. Documentation updates

---

## Success Metrics

- **Reliability:** App runs 7 days without restart
- **Performance:** Chat response time < 3 seconds (p95)
- **Scalability:** Supports 100 concurrent users
- **Cost:** Gemini API costs < $50/month for 1000 users
- **Quality:** 70% test coverage, zero critical bugs
- **UX:** User can complete signup → chat in < 2 minutes

---

## Risk Mitigation

### Breaking Changes
- Database schema changes require migration scripts
- Frontend API changes need backward compatibility period
- Document all breaking changes in CHANGELOG.md

### Rollback Plan
- Tag current version as `v0.1-pre-fixes`
- Create feature branches for each fix
- Test in staging before production deploy
- Keep database backups before migrations

### Dependencies
- Pin all package versions in requirements.txt
- Test with Python 3.10, 3.11, 3.12
- Document minimum versions for Redis, PostgreSQL

---

## Acceptance Criteria (Overall)

- [ ] All 15 issues resolved
- [ ] Test coverage ≥ 70%
- [ ] App runs without Redis in dev mode
- [ ] App runs without SMTP configured
- [ ] Database abstraction works for SQLite and PostgreSQL
- [ ] Chat history paginated (max 50 messages to AI)
- [ ] Rate limiting enforced on chat endpoint
- [ ] File upload security fixed (no crashes)
- [ ] Frontend simplified (3 main views)
- [ ] API versioning consistent (/api/v1 only)
- [ ] Documentation updated (README, API docs, .env.example)
- [ ] Deployment guide written (Docker + manual)

---

## Next Steps

1. **Review & Approve:** Stakeholder review of requirements
2. **Estimate:** Break down into tasks with time estimates
3. **Prioritize:** Confirm implementation order
4. **Branch:** Create `feature/critical-fixes` branch
5. **Implement:** Follow phase-by-phase approach
6. **Test:** Write tests alongside implementation
7. **Deploy:** Staging → Production with monitoring
8. **Document:** Update all documentation

---

## Appendix A: New Environment Variables

```bash
# Required (Production)
JWT_SECRET_KEY=<min-32-chars>
DATABASE_URL=postgresql://user:pass@host:5432/saaita
ALLOWED_ORIGINS=https://app.saaita.com
GEMINI_API_KEY=<your-key>

# Optional (with defaults)
ENVIRONMENT=production  # development|staging|production
REDIS_ENABLED=true      # true|false
REDIS_URL=redis://localhost:6379/0
SMTP_ENABLED=false      # true|false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@saaita.com
SMTP_PASS=<password>
EMAIL_FROM=noreply@saaita.com
APP_URL=https://app.saaita.com
RATE_LIMIT_ENABLED=true
MAX_CHAT_MESSAGES_PER_HOUR=20
MAX_TOKENS_PER_DAY=100000
```

---

## Appendix B: New Database Tables

```sql
-- Pending emails (for retry)
CREATE TABLE pending_emails (
    id SERIAL PRIMARY KEY,
    to_address TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- API usage tracking
CREATE TABLE api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    endpoint TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Pending audit logs (for retry)
CREATE TABLE pending_audit_logs (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    ip_address TEXT,
    details TEXT,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chat messages archive (>90 days)
CREATE TABLE chat_messages_archive (
    -- Same schema as chat_messages
    -- Moved here by background job
);
```

---

**Document Owner:** Development Team  
**Last Updated:** 2026-04-14  
**Status:** Ready for Review

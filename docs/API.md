# SAAITA API Documentation

FIX 2.22: OpenAPI 3.0 specification for complete API documentation

## Quick Links

- **OpenAPI Spec:** [openapi.yaml](./openapi.yaml)
- **Swagger UI:** `http://localhost:5000/api/docs` (when running locally)
- **ReDoc:** `http://localhost:5000/api/redoc`

## Authentication

### Token Types

| Token | Storage | Lifetime | Purpose |
|-------|---------|----------|---------|
| `access_token` | httpOnly cookie | 15 minutes | API authorization |
| `refresh_token` | httpOnly cookie | 7 days | Obtain new access token |
| `csrf_token` | localStorage | session | CSRF protection header |

### Request Example

```bash
curl -X POST http://localhost:5000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: your_csrf_token" \
  -d '{
    "prompt": "Hello, AI!"
  }' \
  --cookie "access_token=your_jwt_token"
```

## Error Handling

All endpoints return consistent error format:

```json
{
  "error": "Error message",
  "details": {
    "code": "SPECIFIC_CODE",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Status Codes

| Code | Meaning | Resolution |
|------|---------|-----------|
| 200 | Success | No action needed |
| 400 | Bad request | Fix request format/data |
| 401 | Unauthorized | Refresh token or re-login |
| 403 | Forbidden | User lacks permission |
| 409 | Conflict | Resource already exists |
| 429 | Rate limited | Wait before retrying |
| 500 | Server error | Contact support |
| 503 | Service unavailable | Email service down |

## Rate Limits

Rate limits are enforced per endpoint, per user, using Redis:

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /auth/signup | 3 | hour |
| POST /auth/login | 5 | 15 min |
| POST /auth/refresh | 20 | hour |
| POST /chat/message | unlimited | N/A |

Response headers include:
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1705310400
```

## Versioning

### Current Version
- **Version:** `v1`
- **Base URL:** `/api/v1`
- **Deprecated:** `/api` (legacy, still supported)

### Migration Guide

If you're using the legacy `/api` endpoints:

```javascript
// OLD (still works)
fetch('http://api.example.com/api/auth/login', {...})

// NEW (recommended)
fetch('http://api.example.com/api/v1/auth/login', {...})
```

Both return identical responses. In future versions, breaking changes will be released as `/api/v2` while `/api/v1` remains stable.

## Response Pagination

Chat history supports cursor-based pagination:

```bash
GET /api/v1/chat/history?limit=50&offset=0
```

Response:
```json
{
  "messages": [...],
  "total": 500,
  "page": 1,
  "limit": 50
}
```

## Webhooks (Future)

Planned for v2: Event webhooks for:
- `user.created` - New user signup
- `chat.completed` - Message response received
- `auth.failed` - Failed login attempt
- `token.revoked` - Session revoked

Subscribe at: `POST /api/webhooks/subscribe`

---

**Last Updated:** FIX 2.22 (OpenAPI Documentation)

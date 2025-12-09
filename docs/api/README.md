# API Documentation

Welcome to the Basketball Film Review API documentation. This API provides programmatic access to manage teams, games, clips, players, and statistics.

## Overview

The Basketball Film Review API is a RESTful API built with FastAPI. It supports:

- Team and roster management
- Game video upload and management
- Clip creation with automated processing
- Clip annotations and voice-over
- Player assignments
- Game statistics tracking
- Role-based access control (Coach, Player, Parent)

## Base URL

### Development
```
http://localhost:8000
```

### Production
The API is typically proxied through nginx at:
```
https://your-domain.com/api
```

## Authentication

All API endpoints (except public invite preview) require authentication. The API uses JWT (JSON Web Tokens) for authentication.

[Read the Authentication Guide](authentication.md)

## API Documentation

### Interactive Documentation

When running the application, interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

These interfaces allow you to:
- Browse all endpoints
- See request/response schemas
- Test endpoints directly from your browser
- View detailed error responses

### Endpoints Reference

[View Complete Endpoints Documentation](endpoints.md)

## Quick Start

### 1. Authenticate (Coach)

```bash
# Google OAuth (coaches only)
POST /auth/google
Content-Type: application/json

{
  "code": "google_auth_code_here"
}

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "coach@example.com",
    "role": "coach",
    ...
  }
}
```

### 2. Create a Team

```bash
POST /teams
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Eastside Tigers",
  "season": "Fall 2024"
}

# Response
{
  "id": "team-uuid",
  "name": "Eastside Tigers",
  "season": "Fall 2024",
  "created_by": "coach-uuid",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 3. Upload a Game

```bash
POST /games
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

name=vs Warriors&date=2024-01-20&home_team_color=white&away_team_color=dark&video=@game.mp4
```

### 4. Create a Clip

```bash
POST /clips
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "game_id": "game-uuid",
  "video_id": "video-uuid",
  "start_time": "5:30",
  "end_time": "5:45",
  "tags": ["fast break", "defense"],
  "players": ["John Smith"],
  "notes": "Great defensive rotation"
}

# Response
{
  "id": "clip-uuid",
  "status": "pending",
  ...
}
```

## Rate Limiting

To ensure fair usage and system stability:

- **Authentication endpoints**: 5 requests/minute per IP
- **API endpoints**: 100 requests/minute per authenticated user
- **File uploads**: 10 requests/minute per user

Exceeding these limits returns a `429 Too Many Requests` response.

## Error Handling

The API uses standard HTTP status codes and returns errors in this format:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

## Data Formats

### Timestamps

All timestamps use ISO 8601 format in UTC:
```
2024-01-15T10:30:00Z
```

### UUIDs

All resource IDs are UUIDs in string format:
```
"550e8400-e29b-41d4-a716-446655440000"
```

### Time Formats for Clips

When creating clips, use these timestamp formats:
- Minutes:Seconds - `"5:30"` (5 minutes, 30 seconds)
- Hours:Minutes:Seconds - `"1:15:20"` (1 hour, 15 minutes, 20 seconds)

## Pagination

Currently, the API returns all results without pagination. Future versions may implement pagination for large result sets.

## Versioning

The API does not currently use versioning. Breaking changes will be announced in advance.

## SDKs and Client Libraries

Official SDKs are not yet available. The API can be consumed using any HTTP client library in your preferred language.

### Python Example

```python
import requests

# Authenticate
response = requests.post(
    "http://localhost:8000/auth/login",
    json={
        "username": "player1",
        "password": "secure_password"
    }
)
token = response.json()["access_token"]

# Make authenticated request
headers = {"Authorization": f"Bearer {token}"}
clips = requests.get(
    "http://localhost:8000/me/clips",
    headers=headers
).json()

print(f"You have {len(clips)} assigned clips")
```

### JavaScript Example

```javascript
// Authenticate
const response = await fetch('http://localhost:8000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'player1',
    password: 'secure_password'
  })
});

const { access_token } = await response.json();

// Make authenticated request
const clipsResponse = await fetch('http://localhost:8000/me/clips', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});

const clips = await clipsResponse.json();
console.log(`You have ${clips.length} assigned clips`);
```

## Support

- **Interactive docs**: Use `/docs` for hands-on testing
- **Developer guide**: See [Developer Documentation](../developer/README.md)
- **Issues**: Report bugs via your issue tracking system
- **Questions**: Contact your development team

## Next Steps

- [Authentication Guide](authentication.md) - Learn about auth flows
- [Endpoints Reference](endpoints.md) - Complete endpoint documentation
- [Developer Guide](../developer/README.md) - Set up local development

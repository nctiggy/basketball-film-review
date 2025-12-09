# Authentication

The Basketball Film Review API uses JWT (JSON Web Tokens) for authentication. Different authentication methods are available depending on the user role.

## Authentication Methods

### Coach Authentication

Coaches authenticate using **Google OAuth 2.0**:

```http
POST /auth/google
Content-Type: application/json

{
  "code": "google_authorization_code"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "coach@example.com",
    "display_name": "Coach Smith",
    "role": "coach",
    "status": "active",
    "auth_provider": "google",
    "created_at": "2024-01-15T10:30:00Z",
    "last_login_at": "2024-01-20T14:22:00Z"
  }
}
```

**Notes:**
- First-time sign-in automatically creates a coach account
- Subsequent sign-ins return existing account
- Suspended accounts receive a `403 Forbidden` response

### Player/Parent Authentication

Players and parents authenticate using **username and password**:

```http
POST /auth/login
Content-Type: application/json

{
  "username": "player123",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "username": "player123",
    "display_name": "John Smith",
    "role": "player",
    "status": "active",
    "auth_provider": "local",
    "created_at": "2024-01-10T08:15:00Z",
    "last_login_at": "2024-01-20T18:45:00Z"
  }
}
```

## Account Registration (Players/Parents)

Players and parents register using an invite code:

```http
POST /auth/register
Content-Type: application/json

{
  "invite_code": "ABC123XYZ456",
  "username": "player123",
  "password": "secure_password",
  "display_name": "John Smith",
  "phone": "+1234567890"
}
```

**Response:**
Same format as login response, with newly created user and tokens.

**Error Responses:**
- `400 Bad Request` - Invalid/expired invite code or username already taken
- `422 Unprocessable Entity` - Validation error (weak password, invalid format)

## Using Access Tokens

Include the access token in the `Authorization` header for all authenticated requests:

```http
GET /me/clips
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Expiration

- **Access tokens**: Valid for 24 hours
- **Refresh tokens**: Valid for 7 days

When an access token expires, you'll receive:
```json
{
  "detail": "Token has expired"
}
```

Status code: `401 Unauthorized`

## Refreshing Tokens

Use a refresh token to obtain a new access token without re-authenticating:

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { ... }
}
```

**Notes:**
- The old refresh token is automatically revoked
- A new refresh token is issued
- Revoked tokens cannot be reused

**Error Responses:**
- `401 Unauthorized` - Invalid, expired, or revoked refresh token

## Getting Current User Info

Retrieve information about the authenticated user:

```http
GET /auth/me
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "coach@example.com",
  "username": null,
  "display_name": "Coach Smith",
  "role": "coach",
  "phone": "+1234567890",
  "status": "active",
  "auth_provider": "google",
  "created_at": "2024-01-15T10:30:00Z",
  "last_login_at": "2024-01-20T14:22:00Z"
}
```

## Updating Profile

Update the authenticated user's profile:

```http
PUT /auth/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "display_name": "Coach John Smith",
  "phone": "+1234567890"
}
```

**Response:**
Updated user object (same format as GET /auth/me).

## Changing Password

Change password for local accounts (players/parents only):

```http
PUT /auth/me/password
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response:**
```json
{
  "message": "Password changed successfully"
}
```

**Error Responses:**
- `400 Bad Request` - Cannot change password for OAuth accounts
- `401 Unauthorized` - Current password is incorrect

## Logout

Revoke all refresh tokens for the current user:

```http
POST /auth/logout
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Notes:**
- Revokes all refresh tokens for the user
- Access token remains valid until expiration
- Client should discard both tokens

## Google OAuth Flow (Coaches)

### Step 1: Redirect to Google

Redirect the user to Google's OAuth authorization endpoint:

```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  response_type=code&
  scope=openid email profile&
  access_type=offline&
  prompt=consent
```

### Step 2: Handle Callback

After the user authorizes, Google redirects to your `redirect_uri` with a code:

```
https://your-app.com/auth/callback?code=AUTHORIZATION_CODE
```

### Step 3: Exchange Code for Token

Send the authorization code to the API:

```http
POST /auth/google
Content-Type: application/json

{
  "code": "AUTHORIZATION_CODE"
}
```

The API:
1. Exchanges the code for user info with Google
2. Creates or retrieves the user account
3. Returns access and refresh tokens

## Security Best Practices

### For API Consumers

1. **Store tokens securely**
   - Use secure storage (e.g., encrypted storage, secure cookies)
   - Never store tokens in plain text
   - Never commit tokens to version control

2. **Handle token expiration**
   - Implement automatic token refresh
   - Gracefully handle 401 responses
   - Provide clear re-authentication flow

3. **Use HTTPS**
   - Always use HTTPS in production
   - Never send tokens over HTTP

4. **Implement logout**
   - Call /auth/logout when user signs out
   - Clear stored tokens from client

5. **Validate tokens**
   - Don't trust client-side token validation
   - Always send tokens to the server for verification

### Password Requirements

For local accounts (players/parents):
- Minimum 8 characters
- Passwords are hashed with bcrypt (work factor 12)
- No additional complexity requirements

## Role-Based Access Control

### User Roles

- **coach**: Full access to their teams, roster, clips, and stats
- **player**: Read-only access to assigned clips and personal stats
- **parent**: Read-only access to linked children's clips and stats

### Authorization Checks

Every endpoint verifies:
1. Valid authentication token
2. User has the required role
3. User has access to the requested resource

**Example**: Players can only access clips explicitly assigned to them.

## Error Responses

### 401 Unauthorized

Token is missing, invalid, or expired:
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

User is authenticated but lacks permission:
```json
{
  "detail": "Insufficient permissions"
}
```

Or for suspended accounts:
```json
{
  "detail": "Account suspended"
}
```

### 422 Unprocessable Entity

Request validation failed:
```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

## Testing Authentication

### Example: Complete Auth Flow (Python)

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Login
response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "username": "player123",
        "password": "secure_password"
    }
)
response.raise_for_status()
tokens = response.json()

access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]

# 2. Make authenticated request
headers = {"Authorization": f"Bearer {access_token}"}
user_info = requests.get(
    f"{BASE_URL}/auth/me",
    headers=headers
).json()

print(f"Logged in as: {user_info['display_name']}")

# 3. Refresh token (when access token expires)
new_tokens = requests.post(
    f"{BASE_URL}/auth/refresh",
    json={"refresh_token": refresh_token}
).json()

# 4. Logout
requests.post(
    f"{BASE_URL}/auth/logout",
    headers={"Authorization": f"Bearer {access_token}"}
)
```

### Example: OAuth Flow (JavaScript)

```javascript
// Step 1: Redirect to Google
function initiateGoogleAuth() {
  const params = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID,
    redirect_uri: 'https://your-app.com/auth/callback',
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    prompt: 'consent'
  });

  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

// Step 2: Handle callback
async function handleCallback(code) {
  const response = await fetch('/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  });

  const tokens = await response.json();

  // Store tokens securely
  localStorage.setItem('access_token', tokens.access_token);
  localStorage.setItem('refresh_token', tokens.refresh_token);

  return tokens.user;
}
```

## Rate Limiting

Authentication endpoints have strict rate limits:

- **5 requests/minute per IP address**
- Exceeds return `429 Too Many Requests`

This prevents:
- Brute force password attacks
- Account enumeration
- OAuth code harvesting

## Next Steps

- [Endpoints Reference](endpoints.md) - Explore all available endpoints
- [Developer Guide](../developer/README.md) - Set up local development

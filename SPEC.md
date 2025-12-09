# Basketball Film Review - Feature Specification

This document defines the architecture and requirements for the expanded basketball film review application. All development agents reference this specification.

## Project Overview

A web application for basketball coaches to upload game videos, create timestamped clips, annotate them with drawings and voice-over, and share them with specific players. Players and parents can view assigned clips through a secure, isolated dashboard.

## Architecture

### Stack
- **Backend**: Python FastAPI (modular structure)
- **Frontend**: Vanilla HTML/CSS/JavaScript (single SPA, role-based views)
- **Database**: PostgreSQL with asyncpg
- **Storage**: MinIO S3-compatible object storage
- **Video Processing**: ffmpeg
- **Deployment**: Kubernetes via Helm, Flux CD for GitOps

### Project Structure
```
basketball-film-review/
├── backend/
│   ├── app.py              # Main FastAPI app, router registration
│   ├── auth/               # Authentication module
│   │   ├── __init__.py
│   │   ├── jwt.py          # JWT utilities
│   │   ├── oauth.py        # Google OAuth handlers
│   │   ├── password.py     # Password hashing
│   │   └── dependencies.py # FastAPI dependencies (get_current_user, etc.)
│   ├── middleware/         # Middleware
│   │   ├── __init__.py
│   │   └── auth.py         # Auth middleware
│   ├── routes/             # Route modules
│   │   ├── __init__.py
│   │   ├── auth.py         # /auth/* endpoints
│   │   ├── teams.py        # /teams/* endpoints
│   │   ├── players.py      # /players/* endpoints
│   │   ├── clips.py        # /clips/* endpoints (extends existing)
│   │   ├── games.py        # /games/* endpoints (extends existing)
│   │   ├── invites.py      # /invites/* endpoints
│   │   └── stats.py        # /stats/* endpoints
│   ├── models/             # Pydantic models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── team.py
│   │   ├── clip.py
│   │   └── stats.py
│   └── utils/              # Utilities
│       ├── __init__.py
│       └── db.py           # Database helpers
├── frontend/
│   ├── index.html          # Single SPA entry point
│   ├── css/
│   │   └── styles.css      # All styles
│   └── js/
│       ├── app.js          # Main app, routing, state
│       ├── api.js          # API client
│       ├── auth.js         # Auth utilities, token management
│       ├── components/     # UI components
│       │   ├── header.js
│       │   ├── sidebar.js
│       │   ├── teams.js
│       │   ├── roster.js
│       │   ├── clips.js
│       │   ├── annotations.js
│       │   ├── stats.js
│       │   └── player-dashboard.js
│       └── lib/            # Third-party (Fabric.js, etc.)
├── migrations/             # Database migrations
│   └── 001_initial.sql
├── tests/                  # Test suite
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── e2e/
├── helm/                   # Kubernetes deployment
├── docs/                   # Documentation
└── SPEC.md                 # This file
```

## User Roles

### Coach
- Full access to teams they own or assist
- Create/manage teams, roster, games, clips
- Annotate clips with drawings and audio
- Assign clips to specific players
- Enter and edit player stats
- Invite players and parents
- View all data for their teams

### Player
- View ONLY clips explicitly assigned to them
- View ONLY their own stats
- View team roster (names only, no other players' data)
- Mark clips as viewed/acknowledged
- Update own profile (display name, password)
- **Cannot** see other players' clips or stats
- **Cannot** modify any content

### Parent
- View ONLY data for their linked children
- Same view as their child (read-only)
- Can have multiple children linked
- **Cannot** see other children's data
- **Cannot** modify any content

## Database Schema

### Unified Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    username TEXT UNIQUE,
    password_hash TEXT,
    auth_provider TEXT DEFAULT 'local',       -- 'google', 'local'
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('coach', 'player', 'parent')),
    phone TEXT,
    status TEXT DEFAULT 'invited',            -- 'invited', 'active', 'suspended'
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    CONSTRAINT email_or_username CHECK (email IS NOT NULL OR username IS NOT NULL)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
```

### Player Profiles (optional extras)
```sql
CREATE TABLE player_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    jersey_number TEXT,
    position TEXT,                            -- 'PG', 'SG', 'SF', 'PF', 'C'
    graduation_year INTEGER
);
```

### Parent-Player Links
```sql
CREATE TABLE parent_links (
    parent_id UUID REFERENCES users(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    verified_at TIMESTAMP,
    PRIMARY KEY (parent_id, player_id)
);

CREATE INDEX idx_parent_links_parent ON parent_links(parent_id);
CREATE INDEX idx_parent_links_player ON parent_links(player_id);
```

### Teams
```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    season TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Team-Coach Relationship (multiple coaches per team)
```sql
CREATE TABLE team_coaches (
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    coach_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'assistant',            -- 'head', 'assistant'
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (team_id, coach_id)
);

CREATE INDEX idx_team_coaches_coach ON team_coaches(coach_id);
```

### Team-Player Relationship
```sql
CREATE TABLE team_players (
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (team_id, player_id)
);

CREATE INDEX idx_team_players_player ON team_players(player_id);
```

### Invites
```sql
CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    target_role TEXT NOT NULL,                -- 'player', 'parent'
    target_name TEXT,                         -- Pre-filled name
    linked_player_id UUID REFERENCES users(id), -- For parent invites
    expires_at TIMESTAMP NOT NULL,
    claimed_by UUID REFERENCES users(id),
    claimed_at TIMESTAMP,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invites_code ON invites(code);
CREATE INDEX idx_invites_team ON invites(team_id);
```

### Games (modified - add team_id)
```sql
ALTER TABLE games ADD COLUMN team_id UUID REFERENCES teams(id);
CREATE INDEX idx_games_team ON games(team_id);
```

### Clip Assignments
```sql
CREATE TABLE clip_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id),
    message TEXT,
    priority TEXT DEFAULT 'normal',           -- 'high', 'normal', 'low'
    viewed_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clip_id, player_id)
);

CREATE INDEX idx_clip_assignments_player ON clip_assignments(player_id);
CREATE INDEX idx_clip_assignments_clip ON clip_assignments(clip_id);
```

### Clip Annotations
```sql
CREATE TABLE clip_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    drawing_data JSONB,                       -- Fabric.js canvas state
    audio_path TEXT,                          -- MinIO path to audio file
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_clip_annotations_clip ON clip_annotations(clip_id);
```

### Player Game Stats
```sql
CREATE TABLE player_game_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Scoring
    points INTEGER DEFAULT 0,
    field_goals_made INTEGER DEFAULT 0,
    field_goals_attempted INTEGER DEFAULT 0,
    three_pointers_made INTEGER DEFAULT 0,
    three_pointers_attempted INTEGER DEFAULT 0,
    free_throws_made INTEGER DEFAULT 0,
    free_throws_attempted INTEGER DEFAULT 0,

    -- Rebounds
    offensive_rebounds INTEGER DEFAULT 0,
    defensive_rebounds INTEGER DEFAULT 0,

    -- Other
    assists INTEGER DEFAULT 0,
    steals INTEGER DEFAULT 0,
    blocks INTEGER DEFAULT 0,
    turnovers INTEGER DEFAULT 0,
    fouls INTEGER DEFAULT 0,
    minutes_played INTEGER,

    recorded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(game_id, player_id)
);

CREATE INDEX idx_player_game_stats_player ON player_game_stats(player_id);
CREATE INDEX idx_player_game_stats_game ON player_game_stats(game_id);
```

### Notifications (for future)
```sql
CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    notify_new_clip BOOLEAN DEFAULT true,
    notify_new_message BOOLEAN DEFAULT true
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    data JSONB,
    read_at TIMESTAMP,
    sent_email_at TIMESTAMP,
    sent_sms_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE read_at IS NULL;
```

### Live Streams (for future)
```sql
CREATE TABLE live_streams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    stream_key TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'inactive',           -- 'inactive', 'live', 'ended'
    rtsp_url TEXT,
    hls_url TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Conventions

### Base URL
- Development: `http://localhost:8000`
- Production: Proxied through nginx at `/api`

### Authentication
- JWT tokens in Authorization header: `Authorization: Bearer <token>`
- Tokens expire after 24 hours
- Refresh tokens valid for 7 days

### Response Format
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Error Format
```json
{
  "detail": "Error message here"
}
```

### Status Codes
- 200: Success
- 201: Created
- 400: Bad request (validation error)
- 401: Not authenticated
- 403: Not authorized (wrong role or no access)
- 404: Not found
- 422: Validation error (Pydantic)
- 500: Server error

## API Endpoints

### Authentication
```
POST /auth/google          # Google OAuth callback
POST /auth/login           # Username/password login
POST /auth/register        # Create account (via invite)
POST /auth/refresh         # Refresh JWT token
GET  /auth/me              # Get current user
PUT  /auth/me              # Update profile
PUT  /auth/me/password     # Change password
POST /auth/logout          # Invalidate token
```

### Teams (Coach only)
```
GET    /teams              # List coach's teams
POST   /teams              # Create team
GET    /teams/{id}         # Get team details
PUT    /teams/{id}         # Update team
DELETE /teams/{id}         # Delete team

GET    /teams/{id}/coaches    # List team coaches
POST   /teams/{id}/coaches    # Add coach to team
DELETE /teams/{id}/coaches/{coach_id}  # Remove coach

GET    /teams/{id}/players    # List team players (roster)
POST   /teams/{id}/players    # Add player to team (creates invite)
DELETE /teams/{id}/players/{player_id}  # Remove player
```

### Invites
```
GET  /invites              # List invites (coach: their invites, others: N/A)
POST /invites              # Create invite (coach only)
GET  /invites/{code}       # Preview invite (public, for claim page)
POST /invites/{code}/claim # Claim invite, create account
DELETE /invites/{id}       # Revoke invite (coach only)
```

### Games (modified)
```
GET    /games              # List games (filtered by team for coach)
POST   /games              # Create game (must specify team_id)
GET    /games/{id}         # Get game details
PUT    /games/{id}         # Update game
DELETE /games/{id}         # Delete game
```

### Clips (modified)
```
GET  /clips                # List clips (coach: by team, player: assigned only)
POST /clips                # Create clip
GET  /clips/{id}           # Get clip (auth checked)
PUT  /clips/{id}           # Update clip
DELETE /clips/{id}         # Delete clip

POST /clips/{id}/assign    # Assign clip to player(s)
GET  /clips/{id}/assignments  # List assignments for clip
DELETE /clips/{id}/assignments/{player_id}  # Remove assignment

POST /clips/{id}/viewed    # Mark as viewed (player)
POST /clips/{id}/acknowledge  # Acknowledge review (player)
```

### Annotations (Coach only for write)
```
GET  /clips/{id}/annotations  # Get annotations for clip
POST /clips/{id}/annotations  # Create/update annotations
POST /clips/{id}/audio        # Upload audio overlay
GET  /clips/{id}/audio        # Get audio overlay
DELETE /clips/{id}/audio      # Delete audio overlay
```

### Stats
```
GET  /games/{id}/stats        # Get all player stats for game
POST /games/{id}/stats        # Add/update stats (coach only)
GET  /players/{id}/stats      # Get player's stats (filtered by access)
GET  /teams/{id}/stats        # Get team aggregate stats (coach only)
```

### Player/Parent Specific
```
GET /me/clips              # Player: assigned clips, Parent: children's clips
GET /me/stats              # Player: own stats
GET /me/teams              # Player: teams they're on
GET /me/children           # Parent: linked children
GET /me/children/{id}/clips   # Parent: specific child's clips
GET /me/children/{id}/stats   # Parent: specific child's stats
```

## Frontend Patterns

### State Management
```javascript
// Simple global state
const state = {
  user: null,           // Current user
  token: null,          // JWT token
  teams: [],            // Coach's teams
  currentTeam: null,    // Selected team
  clips: [],            // Current clip list
  // ...
};

// Update state and re-render
function setState(updates) {
  Object.assign(state, updates);
  render();
}
```

### API Client
```javascript
// api.js
const API_BASE = '/api';

async function api(endpoint, options = {}) {
  const token = localStorage.getItem('token');
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'API error');
  }

  return response.json();
}

// Usage
const teams = await api('/teams');
const team = await api('/teams', { method: 'POST', body: JSON.stringify({ name: 'Tigers' }) });
```

### Role-Based Rendering
```javascript
// app.js
function render() {
  const app = document.getElementById('app');

  if (!state.user) {
    app.innerHTML = renderLoginPage();
    return;
  }

  switch (state.user.role) {
    case 'coach':
      app.innerHTML = renderCoachDashboard();
      break;
    case 'player':
      app.innerHTML = renderPlayerDashboard();
      break;
    case 'parent':
      app.innerHTML = renderParentDashboard();
      break;
  }
}
```

### Component Pattern
```javascript
// components/teams.js
function TeamList(teams) {
  return `
    <div class="team-list">
      ${teams.map(team => `
        <div class="team-card" onclick="selectTeam('${team.id}')">
          <h3>${team.name}</h3>
          <p>${team.season || ''}</p>
        </div>
      `).join('')}
    </div>
  `;
}
```

## Security Requirements

### Authentication
- Passwords hashed with bcrypt (work factor 12)
- JWT signed with HS256, 24-hour expiration
- Refresh tokens stored securely, 7-day expiration
- Google OAuth with state parameter validation

### Authorization
- Every endpoint must check authentication
- Every endpoint must verify role and resource access
- Players can ONLY access assigned clips
- Parents can ONLY access linked children's data
- Use parameterized queries everywhere (no SQL injection)

### Input Validation
- All input validated with Pydantic models
- File uploads validated (type, size)
- HTML output escaped (XSS prevention)

### Rate Limiting
- Auth endpoints: 5 requests/minute per IP
- API endpoints: 100 requests/minute per user
- File uploads: 10/minute per user

## Testing Requirements

### Unit Tests
- Auth utilities (JWT, password hashing)
- Validation functions
- Utility functions

### Integration Tests
- Every API endpoint (happy path + error cases)
- Database operations
- File operations (MinIO)

### Security Tests
- Access control for every endpoint
- Player A cannot access Player B's data
- Parent cannot access non-linked children
- Invalid/expired tokens rejected

### E2E Tests
- Coach: Login → Create team → Add player → Assign clip
- Player: Claim invite → Login → View clip
- Parent: Claim invite → Login → View child's clips

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx
MINIO_BUCKET=basketball-clips

# Auth
JWT_SECRET=your-secret-key
JWT_EXPIRATION_HOURS=24
REFRESH_TOKEN_DAYS=7
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx

# Future: Notifications
SENDGRID_API_KEY=xxx
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=xxx
```

### Secrets Management (1Password)

The cluster has the **1Password Operator** installed for secrets management. Use 1Password for all sensitive values rather than storing secrets directly in Helm values or Kubernetes secrets.

#### How It Works

1. Store secrets in 1Password vault
2. Create a `OnePasswordItem` CRD that references the vault item
3. The operator automatically creates/syncs a Kubernetes Secret
4. Reference the Secret in your deployments

#### Example OnePasswordItem

```yaml
apiVersion: onepassword.com/v1
kind: OnePasswordItem
metadata:
  name: basketball-film-review-secrets
  namespace: film-review
spec:
  itemPath: "vaults/Kubernetes/items/basketball-film-review"
```

This creates a Kubernetes Secret named `basketball-film-review-secrets` with all fields from the 1Password item.

#### Required 1Password Fields

Create a 1Password item with these fields:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret key for JWT signing
- `MINIO_ACCESS_KEY` - MinIO access key
- `MINIO_SECRET_KEY` - MinIO secret key
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret

#### Referencing in Deployments

```yaml
env:
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: basketball-film-review-secrets
        key: JWT_SECRET
```

#### Benefits

- Secrets never stored in Git
- Automatic rotation support
- Single source of truth
- Audit logging via 1Password

## Annotation Data Format

```json
{
  "version": "1.0",
  "canvasWidth": 1280,
  "canvasHeight": 720,
  "objects": [
    {
      "type": "arrow",
      "id": "a1b2c3",
      "startTime": 2.5,
      "endTime": 5.0,
      "x1": 100,
      "y1": 200,
      "x2": 300,
      "y2": 150,
      "stroke": "#ff0000",
      "strokeWidth": 4
    },
    {
      "type": "circle",
      "id": "d4e5f6",
      "startTime": 3.0,
      "endTime": 6.0,
      "left": 400,
      "top": 300,
      "radius": 50,
      "stroke": "#ffff00",
      "strokeWidth": 3,
      "fill": "transparent"
    },
    {
      "type": "path",
      "id": "g7h8i9",
      "startTime": 4.0,
      "endTime": 8.0,
      "path": "M 10 20 L 15 25 L 20 22...",
      "stroke": "#00ff00",
      "strokeWidth": 2
    },
    {
      "type": "textbox",
      "id": "j0k1l2",
      "startTime": 2.0,
      "endTime": 7.0,
      "left": 500,
      "top": 100,
      "text": "Watch the screen!",
      "fontSize": 24,
      "fill": "#ffffff",
      "backgroundColor": "rgba(0,0,0,0.7)"
    }
  ]
}
```

## Progress Tracking

Agents update this section as they complete work:

### Agent 1: Foundation
- [x] Database migration script
- [x] Auth module (JWT, OAuth, password)
- [x] Auth dependencies (get_current_user, require_role)
- [x] Auth routes (/auth/*)
- [x] Middleware setup

### Agent 2: Coach Side
- [x] Backend: Team models (TeamCreate, TeamUpdate, TeamResponse, etc.)
- [x] Backend: Teams routes (GET/POST /teams, GET/PUT/DELETE /teams/{id})
- [x] Backend: Roster management (GET/POST/DELETE /teams/{id}/players)
- [x] Backend: Coach management (GET/POST/DELETE /teams/{id}/coaches)
- [x] Backend: Invite models (InviteCreate, InviteResponse, InvitePreview)
- [x] Backend: Invite routes (GET/POST /invites, GET /invites/{code}, DELETE /invites/{id})
- [x] Backend: Assignment models (ClipAssignRequest, ClipAssignmentResponse)
- [x] Backend: Clip assignment routes (POST /clips/{id}/assign, GET /clips/{id}/assignments, DELETE /clips/{id}/assignments/{player_id})
- [x] Backend: Annotation models (AnnotationData, AnnotationResponse)
- [x] Backend: Annotations routes (GET/POST /clips/{id}/annotations, POST/GET/DELETE /clips/{id}/audio)
- [x] Backend: Stats models (PlayerGameStats, GameStatsRequest, etc.)
- [x] Backend: Stats routes (GET/POST /games/{id}/stats, GET /players/{id}/stats, GET /teams/{id}/stats)
- [x] Backend: Router registration in app.py
- [ ] Frontend: Coach dashboard UI (team management)
- [ ] Frontend: Roster management UI (add players, generate invites)
- [ ] Frontend: Clip assignment modal (select players)
- [ ] Frontend: Fabric.js canvas integration for drawing annotations
- [ ] Frontend: Audio recording controls (MediaRecorder API)
- [ ] Frontend: Stats entry form

### Agent 3: Player Side
- [x] Backend: Player models (PlayerClipResponse, PlayerStatsResponse, etc.)
- [x] Backend: Player routes (GET /me/clips, /me/stats, /me/teams, POST /me/clips/{id}/viewed, /me/clips/{id}/acknowledge)
- [x] Backend: Parent models (ChildResponse)
- [x] Backend: Parent routes (GET /me/children, /me/children/{id}/clips, /me/children/{id}/stats)
- [x] Backend: Invite preview endpoint (GET /invites/{code})
- [x] Backend: Annotations endpoint (GET /clips/{id}/annotations, GET /clips/{id}/audio)
- [x] Backend: Authorization for clip streaming (players/parents can only access assigned clips)
- [x] Frontend: player-parent.html (complete standalone SPA)
- [x] Frontend: Invite claim flow with hash routing (#/join/{code})
- [x] Frontend: Player dashboard (clips, stats)
- [x] Frontend: Parent dashboard with child selector
- [x] Frontend: Clip viewer with annotation playback (canvas overlay + audio sync)
- [x] Frontend: Mobile-responsive design

### Agent 4: Test Engineer
- [x] Test fixtures (conftest.py with comprehensive fixtures)
- [x] Unit tests (test_auth.py, test_validators.py)
- [x] Integration tests (test_auth_api.py, test_teams_api.py, test_assignments_api.py, test_player_api.py, test_parent_api.py)
- [x] Security tests (test_access_control.py, test_input_validation.py)
- [x] Test utilities (tests/utils.py)
- [x] CI/CD workflow (.github/workflows/test.yml)
- [x] Test documentation (tests/README.md)
- [ ] E2E tests (not implemented - focus on security/integration)

### Agent 5: Security
- [x] Security audit (SECURITY_AUDIT.md created)
- [x] Access control verification (all endpoints reviewed)
- [x] Rate limiting (middleware implemented)
- [x] Security headers (middleware implemented)
- [x] Audit logging (utils/audit_log.py implemented)
- [x] Authentication added to all legacy endpoints
- [x] Fixed all Critical and High severity issues

### Agent 6: DevOps
- [x] Migration scripts (backend/migrate.py with tracking and idempotency)
- [x] Helm updates (auth secrets, init containers, ConfigMap for migrations)
- [x] CI/CD updates (test and security scanning stages added)
- [x] Secret management (auth-secret template, values-auth-example.yaml)

### Agent 7: Documentation
- [x] User guides (coach, player, parent guides created in docs/user-guide/)
- [x] API documentation (README, authentication, complete endpoints reference in docs/api/)
- [x] Developer guide (setup, architecture, contributing in docs/developer/)
- [x] Operations guide (deployment, monitoring, troubleshooting in docs/operations/)

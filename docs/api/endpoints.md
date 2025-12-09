# API Endpoints Reference

Complete reference for all Basketball Film Review API endpoints.

## Table of Contents

- [Authentication](#authentication)
- [Teams](#teams)
- [Invites](#invites)
- [Games](#games)
- [Videos](#videos)
- [Clips](#clips)
- [Clip Assignments](#clip-assignments)
- [Annotations](#annotations)
- [Statistics](#statistics)
- [Player Endpoints](#player-endpoints)
- [Parent Endpoints](#parent-endpoints)

---

## Authentication

### POST /auth/google

Authenticate using Google OAuth (coaches only).

**Authentication:** None (public endpoint)

**Request Body:**
```json
{
  "code": "google_authorization_code"
}
```

**Response (201):**
```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "coach@example.com",
    "display_name": "Coach Smith",
    "role": "coach",
    "status": "active",
    "auth_provider": "google",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Errors:**
- `400` - Invalid authorization code
- `403` - Account suspended
- `500` - Google authentication failed

---

### POST /auth/login

Authenticate using username/password (players/parents).

**Authentication:** None (public endpoint)

**Request Body:**
```json
{
  "username": "player123",
  "password": "secure_password"
}
```

**Response (200):**
Same format as /auth/google

**Errors:**
- `401` - Invalid username or password
- `403` - Account suspended

---

### POST /auth/register

Register a new account using an invite code.

**Authentication:** None (public endpoint)

**Request Body:**
```json
{
  "invite_code": "ABC123XYZ456",
  "username": "player123",
  "password": "secure_password",
  "display_name": "John Smith",
  "phone": "+1234567890"
}
```

**Response (200):**
Same format as /auth/login

**Errors:**
- `400` - Invalid/expired invite code or username taken
- `422` - Validation error

---

### POST /auth/refresh

Refresh an access token.

**Authentication:** None (uses refresh token in body)

**Request Body:**
```json
{
  "refresh_token": "jwt_refresh_token"
}
```

**Response (200):**
Same format as /auth/login

**Errors:**
- `401` - Invalid or expired refresh token

---

### GET /auth/me

Get current user information.

**Authentication:** Required (any role)

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "player123",
  "display_name": "John Smith",
  "role": "player",
  "phone": "+1234567890",
  "status": "active",
  "auth_provider": "local",
  "created_at": "2024-01-15T10:30:00Z",
  "last_login_at": "2024-01-20T14:22:00Z"
}
```

---

### PUT /auth/me

Update current user's profile.

**Authentication:** Required (any role)

**Request Body:**
```json
{
  "display_name": "New Name",
  "phone": "+1234567890"
}
```

**Response (200):**
Updated user object (same format as GET /auth/me)

---

### PUT /auth/me/password

Change password (local accounts only).

**Authentication:** Required (player/parent with local auth)

**Request Body:**
```json
{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response (200):**
```json
{
  "message": "Password changed successfully"
}
```

**Errors:**
- `400` - Cannot change password for OAuth accounts
- `401` - Current password incorrect

---

### POST /auth/logout

Logout and revoke refresh tokens.

**Authentication:** Required (any role)

**Response (200):**
```json
{
  "message": "Logged out successfully"
}
```

---

## Teams

### GET /teams

List all teams the coach is associated with.

**Authentication:** Required (coach only)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "Eastside Tigers",
    "season": "Fall 2024",
    "created_by": "coach_uuid",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### POST /teams

Create a new team.

**Authentication:** Required (coach only)

**Request Body:**
```json
{
  "name": "Eastside Tigers",
  "season": "Fall 2024"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "Eastside Tigers",
  "season": "Fall 2024",
  "created_by": "coach_uuid",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### GET /teams/{team_id}

Get details for a specific team.

**Authentication:** Required (coach with team access)

**Response (200):**
Same format as team object

**Errors:**
- `403` - No access to this team
- `404` - Team not found

---

### PUT /teams/{team_id}

Update team details.

**Authentication:** Required (coach with team access)

**Request Body:**
```json
{
  "name": "Updated Team Name",
  "season": "Spring 2025"
}
```

**Response (200):**
Updated team object

---

### DELETE /teams/{team_id}

Delete a team (creator only).

**Authentication:** Required (team creator)

**Response (204):** No content

**Errors:**
- `403` - Only creator can delete team
- `404` - Team not found

---

### GET /teams/{team_id}/coaches

List all coaches for a team.

**Authentication:** Required (coach with team access)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "display_name": "Coach Smith",
    "email": "coach@example.com",
    "role": "head",
    "added_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### POST /teams/{team_id}/coaches

Add a coach to the team.

**Authentication:** Required (head coach)

**Request Body:**
```json
{
  "coach_id": "coach_uuid",
  "role": "assistant"
}
```

**Response (201):**
Coach object

**Errors:**
- `400` - Coach already on team
- `403` - Only head coaches can add coaches
- `404` - Coach not found

---

### DELETE /teams/{team_id}/coaches/{coach_id}

Remove a coach from the team.

**Authentication:** Required (head coach)

**Response (204):** No content

**Errors:**
- `400` - Cannot remove last coach
- `403` - Only head coaches can remove coaches
- `404` - Coach not found on team

---

### GET /teams/{team_id}/players

List all players on the team roster.

**Authentication:** Required (coach with team access)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "display_name": "John Smith",
    "username": "player123",
    "jersey_number": "23",
    "position": "PG",
    "graduation_year": 2026,
    "status": "active",
    "added_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### POST /teams/{team_id}/players

Add a player to the team (creates invite).

**Authentication:** Required (coach with team access)

**Request Body:**
```json
{
  "display_name": "John Smith",
  "jersey_number": "23",
  "position": "PG",
  "graduation_year": 2026
}
```

**Response (201):**
```json
{
  "player": {
    "id": "uuid",
    "display_name": "John Smith",
    "status": "invited",
    "added_at": "2024-01-15T10:30:00Z"
  },
  "invite": {
    "id": "uuid",
    "code": "ABC123XYZ456",
    "expires_at": "2024-02-14T10:30:00Z"
  }
}
```

---

### DELETE /teams/{team_id}/players/{player_id}

Remove a player from the team roster.

**Authentication:** Required (coach with team access)

**Response (204):** No content

**Errors:**
- `404` - Player not found on team

---

## Invites

### GET /invites

List all invites created by the current coach.

**Authentication:** Required (coach only)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "code": "ABC123XYZ456",
    "team_id": "team_uuid",
    "target_role": "player",
    "target_name": "John Smith",
    "linked_player_id": null,
    "expires_at": "2024-02-14T10:30:00Z",
    "claimed_by": null,
    "claimed_at": null,
    "created_by": "coach_uuid",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### POST /invites

Create a new invite code.

**Authentication:** Required (coach with team access)

**Request Body:**
```json
{
  "team_id": "team_uuid",
  "target_role": "player",
  "target_name": "John Smith",
  "linked_player_id": null,
  "expires_in_days": 30
}
```

For parent invites:
```json
{
  "team_id": "team_uuid",
  "target_role": "parent",
  "target_name": "Jane Smith",
  "linked_player_id": "player_uuid",
  "expires_in_days": 30
}
```

**Response (201):**
Invite object

**Errors:**
- `400` - Parent invites require linked_player_id
- `403` - No access to team

---

### GET /invites/{code}

Preview an invite code (public endpoint).

**Authentication:** None (public endpoint)

**Response (200):**
```json
{
  "code": "ABC123XYZ456",
  "team_name": "Eastside Tigers",
  "target_role": "player",
  "target_name": "John Smith",
  "expires_at": "2024-02-14T10:30:00Z",
  "is_valid": true,
  "linked_player_name": null
}
```

**Errors:**
- `404` - Invite not found

---

### DELETE /invites/{invite_id}

Revoke an invite code.

**Authentication:** Required (invite creator)

**Response (204):** No content

**Errors:**
- `403` - Only creator can revoke
- `404` - Invite not found

---

## Games

### GET /games

List all games.

**Authentication:** Required (any role)

**Query Parameters:**
- None

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "vs Warriors - Home Game",
    "date": "2024-01-20",
    "home_team_color": "white",
    "away_team_color": "dark",
    "created_at": "2024-01-15T10:30:00Z",
    "video_count": 1
  }
]
```

---

### POST /games

Create a new game.

**Authentication:** Required (coach only)

**Content-Type:** multipart/form-data

**Form Fields:**
- `name`: Game name (required)
- `date`: Game date in YYYY-MM-DD format (required)
- `home_team_color`: Home team jersey color (default: "white")
- `away_team_color`: Away team jersey color (default: "dark")

**Response (201):**
Game object

**Errors:**
- `400` - Invalid date format

---

### GET /games/{game_id}

Get a specific game.

**Authentication:** Required (any role)

**Response (200):**
Game object

**Errors:**
- `404` - Game not found

---

### PUT /games/{game_id}

Update a game.

**Authentication:** Required (coach only)

**Content-Type:** multipart/form-data

**Form Fields:**
Same as POST /games

**Response (200):**
Updated game object

---

### DELETE /games/{game_id}

Delete a game and all associated videos and clips.

**Authentication:** Required (coach only)

**Response (200):**
```json
{
  "message": "Game deleted successfully"
}
```

**Errors:**
- `404` - Game not found

---

## Videos

### POST /games/{game_id}/videos

Upload a video for a game.

**Authentication:** Required (coach only)

**Content-Type:** multipart/form-data

**Form Fields:**
- `video`: Video file (required)

**Response (201):**
```json
{
  "id": "uuid",
  "game_id": "game_uuid",
  "filename": "game_video.mp4",
  "video_path": "games/game_uuid/video_uuid_game_video.mp4",
  "uploaded_at": "2024-01-15T10:30:00Z"
}
```

**Errors:**
- `404` - Game not found

---

### GET /games/{game_id}/videos

List all videos for a game.

**Authentication:** Required (any role)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "game_id": "game_uuid",
    "filename": "game_video.mp4",
    "video_path": "games/game_uuid/video_uuid_game_video.mp4",
    "uploaded_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### GET /videos/{video_id}

Get a specific video.

**Authentication:** Required (any role)

**Response (200):**
Video object

**Errors:**
- `404` - Video not found

---

### PUT /videos/{video_id}

Update video metadata (filename only).

**Authentication:** Required (coach only)

**Content-Type:** multipart/form-data

**Form Fields:**
- `filename`: New filename (required)

**Response (200):**
Updated video object

---

### DELETE /videos/{video_id}

Delete a video and all associated clips.

**Authentication:** Required (coach only)

**Response (200):**
```json
{
  "message": "Video deleted successfully"
}
```

**Errors:**
- `404` - Video not found

---

### GET /videos/{video_id}/stream

Stream a video with range request support.

**Authentication:** Required (any role)

**Response (200 or 206):**
Video stream (video/mp4)

**Headers:**
- `Accept-Ranges: bytes`
- `Content-Range: bytes start-end/total` (for range requests)

**Errors:**
- `404` - Video not found

---

## Clips

### POST /clips

Create a new clip.

**Authentication:** Required (coach only)

**Request Body:**
```json
{
  "game_id": "game_uuid",
  "video_id": "video_uuid",
  "start_time": "5:30",
  "end_time": "5:45",
  "tags": ["fast break", "defense"],
  "players": ["John Smith"],
  "notes": "Great defensive rotation"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "game_id": "game_uuid",
  "video_id": "video_uuid",
  "start_time": "5:30",
  "end_time": "5:45",
  "tags": ["fast break", "defense"],
  "players": ["John Smith"],
  "notes": "Great defensive rotation",
  "clip_path": null,
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Errors:**
- `404` - Video not found

---

### GET /clips

List clips with optional filters.

**Authentication:** Required (any role)

**Query Parameters:**
- `game_id` (optional): Filter by game
- `tag` (optional): Filter by tag

**Response (200):**
Array of clip objects

**Notes:**
- Coaches see all clips
- Players see only assigned clips
- Parents see clips assigned to their children

---

### GET /clips/{clip_id}

Get a specific clip.

**Authentication:** Required (any role)

**Response (200):**
Clip object

**Errors:**
- `403` - No access to this clip (players/parents)
- `404` - Clip not found

---

### PUT /clips/{clip_id}

Update clip metadata.

**Authentication:** Required (coach only)

**Request Body:**
Same as POST /clips (all fields required)

**Response (200):**
Updated clip object

---

### DELETE /clips/{clip_id}

Delete a clip.

**Authentication:** Required (coach only)

**Response (200):**
```json
{
  "message": "Clip deleted successfully"
}
```

**Errors:**
- `404` - Clip not found

---

### GET /clips/{clip_id}/stream

Stream a processed clip.

**Authentication:** Required (any role, with authorization check)

**Response (200 or 206):**
Video stream (video/mp4)

**Errors:**
- `400` - Clip not ready (status not "completed")
- `403` - No access to this clip
- `404` - Clip not found

---

### GET /clips/{clip_id}/download

Download a processed clip.

**Authentication:** Required (coach only)

**Response (200):**
Video file (video/mp4) with `Content-Disposition: attachment`

**Errors:**
- `400` - Clip not ready
- `404` - Clip not found or clip file not found

---

## Clip Assignments

### POST /clips/{clip_id}/assign

Assign a clip to one or more players.

**Authentication:** Required (coach with team access)

**Request Body:**
```json
{
  "player_ids": ["player_uuid1", "player_uuid2"],
  "message": "Watch your defensive positioning here",
  "priority": "normal"
}
```

**Priority options:** `"high"`, `"normal"`, `"low"`

**Response (201):**
```json
[
  {
    "id": "assignment_uuid",
    "clip_id": "clip_uuid",
    "player_id": "player_uuid1",
    "player_name": "John Smith",
    "assigned_by": "coach_uuid",
    "message": "Watch your defensive positioning here",
    "priority": "normal",
    "viewed_at": null,
    "acknowledged_at": null,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**Errors:**
- `400` - Clip must belong to game with team, or player not on team
- `403` - No access to team
- `404` - Clip not found

---

### GET /clips/{clip_id}/assignments

List assignments for a clip.

**Authentication:** Required (any role)

**Response (200):**
Array of assignment objects

**Notes:**
- Coaches see all assignments
- Players see only their own assignment
- Parents see assignments for their children

---

### DELETE /clips/{clip_id}/assignments/{player_id}

Remove a clip assignment.

**Authentication:** Required (coach with team access)

**Response (204):** No content

**Errors:**
- `403` - No access to team
- `404` - Assignment not found

---

## Annotations

### GET /clips/{clip_id}/annotations

Get annotations for a clip.

**Authentication:** Required (any role, with authorization check)

**Response (200):**
```json
{
  "id": "uuid",
  "clip_id": "clip_uuid",
  "created_by": "coach_uuid",
  "drawing_data": {
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
      }
    ]
  },
  "audio_path": "annotations/clip_uuid_audio.mp3",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

Or if no annotations exist:
```json
{
  "clip_id": "clip_uuid",
  "drawing_data": null,
  "audio_path": null,
  "version": 0
}
```

**Errors:**
- `403` - No access to clip
- `404` - Clip not found

---

### POST /clips/{clip_id}/annotations

Create or update annotations for a clip.

**Authentication:** Required (coach only)

**Request Body:**
```json
{
  "drawing_data": {
    "version": "1.0",
    "canvasWidth": 1280,
    "canvasHeight": 720,
    "objects": [ ... ]
  }
}
```

**Response (201 or 200):**
Annotation object

---

### POST /clips/{clip_id}/audio

Upload audio overlay for a clip.

**Authentication:** Required (coach only)

**Content-Type:** multipart/form-data

**Form Fields:**
- `audio`: Audio file (required, typically MP3 or WAV)

**Response (201):**
```json
{
  "message": "Audio uploaded successfully",
  "audio_path": "annotations/clip_uuid_audio.mp3"
}
```

---

### GET /clips/{clip_id}/audio

Get audio overlay for a clip.

**Authentication:** Required (any role, with authorization check)

**Response (200):**
Audio stream (audio/mpeg)

**Errors:**
- `403` - No access to clip
- `404` - No audio overlay found

---

### DELETE /clips/{clip_id}/audio

Delete audio overlay for a clip.

**Authentication:** Required (coach only)

**Response (204):** No content

**Errors:**
- `404` - No audio overlay found

---

## Statistics

### GET /games/{game_id}/stats

Get all player stats for a game.

**Authentication:** Required (any role)

**Response (200):**
```json
{
  "game_id": "game_uuid",
  "game_name": "vs Warriors - Home Game",
  "stats": [
    {
      "player_id": "player_uuid",
      "player_name": "John Smith",
      "points": 15,
      "field_goals_made": 6,
      "field_goals_attempted": 12,
      "three_pointers_made": 2,
      "three_pointers_attempted": 5,
      "free_throws_made": 1,
      "free_throws_attempted": 2,
      "offensive_rebounds": 2,
      "defensive_rebounds": 5,
      "assists": 4,
      "steals": 2,
      "blocks": 1,
      "turnovers": 3,
      "fouls": 2,
      "minutes_played": 28
    }
  ]
}
```

**Notes:**
- Coaches see all team stats
- Players see only their own stats
- Parents see their children's stats

**Errors:**
- `403` - No access to team (coaches)
- `404` - Game not found

---

### POST /games/{game_id}/stats

Add or update player stats for a game.

**Authentication:** Required (coach with team access)

**Request Body:**
```json
{
  "stats": [
    {
      "player_id": "player_uuid",
      "points": 15,
      "field_goals_made": 6,
      "field_goals_attempted": 12,
      "three_pointers_made": 2,
      "three_pointers_attempted": 5,
      "free_throws_made": 1,
      "free_throws_attempted": 2,
      "offensive_rebounds": 2,
      "defensive_rebounds": 5,
      "assists": 4,
      "steals": 2,
      "blocks": 1,
      "turnovers": 3,
      "fouls": 2,
      "minutes_played": 28
    }
  ]
}
```

**Response (201):**
```json
{
  "message": "Stats updated for 1 players"
}
```

**Errors:**
- `403` - No access to team
- `404` - Game not found

---

### GET /players/{player_id}/stats

Get aggregate stats for a player.

**Authentication:** Required (any role, with authorization check)

**Response (200):**
```json
{
  "player_id": "player_uuid",
  "player_name": "John Smith",
  "games_played": 10,
  "total_points": 150,
  "total_rebounds": 70,
  "total_assists": 40,
  "avg_points": 15.0,
  "avg_rebounds": 7.0,
  "avg_assists": 4.0,
  "fg_percentage": 45.5,
  "three_pt_percentage": 35.0,
  "ft_percentage": 80.0
}
```

**Notes:**
- Players can only view their own stats
- Coaches can view stats for players on their teams
- Parents can view their children's stats

**Errors:**
- `403` - Cannot view other players' stats
- `404` - Player not found

---

### GET /teams/{team_id}/stats

Get aggregate stats for all players on a team.

**Authentication:** Required (coach with team access)

**Response (200):**
```json
{
  "team_id": "team_uuid",
  "team_name": "Eastside Tigers",
  "total_games": 10,
  "player_stats": [
    {
      "player_id": "player_uuid",
      "player_name": "John Smith",
      "games_played": 10,
      "avg_points": 15.0,
      "avg_rebounds": 7.0,
      "avg_assists": 4.0,
      "fg_percentage": 45.5,
      "three_pt_percentage": 35.0,
      "ft_percentage": 80.0
    }
  ]
}
```

**Errors:**
- `403` - No access to team
- `404` - Team not found

---

## Player Endpoints

### GET /me/clips

Get all clips assigned to the current player.

**Authentication:** Required (player only)

**Response (200):**
```json
[
  {
    "id": "clip_uuid",
    "game_id": "game_uuid",
    "video_id": "video_uuid",
    "start_time": "5:30",
    "end_time": "5:45",
    "tags": ["fast break", "defense"],
    "players": ["John Smith"],
    "notes": "Great defensive rotation",
    "clip_path": "clips/clip_uuid.mp4",
    "status": "completed",
    "created_at": "2024-01-15T10:30:00Z",
    "assignment_id": "assignment_uuid",
    "assigned_by_id": "coach_uuid",
    "assigned_by_name": "Coach Smith",
    "message": "Watch your positioning",
    "priority": "normal",
    "viewed_at": null,
    "acknowledged_at": null,
    "assignment_created_at": "2024-01-15T10:35:00Z",
    "game_name": "vs Warriors - Home Game",
    "game_date": "2024-01-20"
  }
]
```

**Errors:**
- `403` - Only players can access this endpoint

---

### GET /me/stats

Get game-by-game stats for the current player.

**Authentication:** Required (player only)

**Response (200):**
```json
[
  {
    "game_id": "game_uuid",
    "game_name": "vs Warriors - Home Game",
    "game_date": "2024-01-20",
    "points": 15,
    "field_goals_made": 6,
    "field_goals_attempted": 12,
    "three_pointers_made": 2,
    "three_pointers_attempted": 5,
    "free_throws_made": 1,
    "free_throws_attempted": 2,
    "offensive_rebounds": 2,
    "defensive_rebounds": 5,
    "assists": 4,
    "steals": 2,
    "blocks": 1,
    "turnovers": 3,
    "fouls": 2,
    "minutes_played": 28,
    "recorded_at": "2024-01-20T22:00:00Z"
  }
]
```

**Errors:**
- `403` - Only players can access this endpoint

---

### GET /me/stats/season

Get aggregated season stats for the current player.

**Authentication:** Required (player only)

**Response (200):**
```json
{
  "games_played": 10,
  "avg_points": 15.0,
  "avg_rebounds": 7.0,
  "avg_assists": 4.0,
  "fg_percentage": 45.5,
  "three_pt_percentage": 35.0,
  "ft_percentage": 80.0
}
```

---

### GET /me/teams

Get all teams the current player is on.

**Authentication:** Required (player only)

**Response (200):**
```json
[
  {
    "id": "team_uuid",
    "name": "Eastside Tigers",
    "season": "Fall 2024",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### POST /me/clips/{clip_id}/viewed

Mark a clip as viewed by the current player.

**Authentication:** Required (player with clip assignment)

**Response (200):**
```json
{
  "message": "Clip marked as viewed",
  "viewed_at": "2024-01-20T15:30:00Z"
}
```

**Errors:**
- `403` - Only players can access this endpoint
- `404` - Clip not found or not assigned to player

---

### POST /me/clips/{clip_id}/acknowledge

Acknowledge that the player has reviewed the clip.

**Authentication:** Required (player with clip assignment)

**Response (200):**
```json
{
  "message": "Clip acknowledged",
  "acknowledged_at": "2024-01-20T15:35:00Z"
}
```

**Errors:**
- `403` - Only players can access this endpoint
- `404` - Clip not found or not assigned to player

---

## Parent Endpoints

### GET /me/children

Get all children linked to the current parent.

**Authentication:** Required (parent only)

**Response (200):**
```json
[
  {
    "id": "player_uuid",
    "username": "player123",
    "display_name": "John Smith",
    "phone": "+1234567890",
    "linked_at": "2024-01-15T10:30:00Z",
    "jersey_number": "23",
    "position": "PG",
    "graduation_year": 2026
  }
]
```

**Errors:**
- `403` - Only parents can access this endpoint

---

### GET /me/children/{child_id}/clips

Get all clips assigned to a specific child.

**Authentication:** Required (parent linked to child)

**Response (200):**
Same format as GET /me/clips

**Errors:**
- `403` - Child not linked to parent or only parents can access
- `404` - Child not found

---

### GET /me/children/{child_id}/stats

Get game-by-game stats for a specific child.

**Authentication:** Required (parent linked to child)

**Response (200):**
Same format as GET /me/stats

**Errors:**
- `403` - Child not linked to parent or only parents can access

---

### GET /me/children/{child_id}/stats/season

Get aggregated season stats for a specific child.

**Authentication:** Required (parent linked to child)

**Response (200):**
Same format as GET /me/stats/season

**Errors:**
- `403` - Child not linked to parent or only parents can access

---

## Additional Endpoints

### GET /

Root endpoint.

**Authentication:** None

**Response (200):**
```json
{
  "message": "Basketball Film Review API",
  "version": "1.0.0"
}
```

---

### GET /health

Health check endpoint.

**Authentication:** None

**Response (200):**
```json
{
  "status": "healthy"
}
```

---

### GET /players

Get all unique players from clips (legacy endpoint).

**Authentication:** Required (any role)

**Response (200):**
```json
[
  "John Smith",
  "Jane Doe",
  "Bob Johnson"
]
```

---

## Notes

### Authorization Summary

| Endpoint | Coach | Player | Parent |
|----------|-------|--------|--------|
| /auth/* | All | All | All |
| /teams/* | Team access | - | - |
| /invites/* | Creator/team | - | - |
| /games/* | All | All (limited) | All (limited) |
| /clips/* | All | Assigned only | Child's clips |
| /clips/{id}/assign | Team access | - | - |
| /clips/{id}/annotations | All | Assigned only | Child's clips |
| /stats/* | Team access | Own only | Child's only |
| /me/clips | - | Own | - |
| /me/stats | - | Own | - |
| /me/children/* | - | - | Linked children |

### Video Streaming

All video streaming endpoints (`/videos/{id}/stream`, `/clips/{id}/stream`) support HTTP Range requests for seeking and scrubbing.

Include a `Range` header in your request:
```
Range: bytes=0-1023
```

The server responds with:
- `206 Partial Content` for range requests
- `200 OK` for full file requests

### Clip Processing

After creating a clip, it goes through these statuses:
1. `pending` - Waiting to be processed
2. `processing` - ffmpeg is extracting the clip
3. `completed` - Clip is ready to stream/download
4. `failed` - Processing encountered an error

Poll the clip endpoint to check status changes.

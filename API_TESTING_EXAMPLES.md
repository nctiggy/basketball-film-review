# API Testing Examples for Coach Endpoints

Quick reference for testing the new coach endpoints with curl or Postman.

---

## Authentication

First, get a token (assuming you have a coach account via Google OAuth or existing seed data):

```bash
# Login as coach
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "coach@example.com",
    "password": "password123"
  }' | jq -r '.access_token')
```

---

## Teams

### Create Team

```bash
curl -X POST http://localhost:8000/api/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tigers Varsity",
    "season": "2024-2025"
  }'
```

**Response:**
```json
{
  "id": "uuid-here",
  "name": "Tigers Varsity",
  "season": "2024-2025",
  "created_by": "coach-uuid",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### List Teams

```bash
curl -X GET http://localhost:8000/api/teams \
  -H "Authorization: Bearer $TOKEN"
```

### Get Team Details

```bash
TEAM_ID="uuid-from-above"

curl -X GET http://localhost:8000/api/teams/$TEAM_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Update Team

```bash
curl -X PUT http://localhost:8000/api/teams/$TEAM_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tigers Varsity Updated",
    "season": "2024-2025"
  }'
```

---

## Roster Management

### Add Player (Auto-generates Invite)

```bash
curl -X POST http://localhost:8000/api/teams/$TEAM_ID/players \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Smith",
    "jersey_number": "23",
    "position": "PG",
    "graduation_year": 2026
  }'
```

**Response:**
```json
{
  "player": {
    "id": "player-uuid",
    "display_name": "John Smith",
    "status": "invited",
    "added_at": "2024-01-15T10:35:00Z"
  },
  "invite": {
    "id": "invite-uuid",
    "code": "abc123def456",
    "expires_at": "2024-02-14T10:35:00Z"
  }
}
```

### List Roster

```bash
curl -X GET http://localhost:8000/api/teams/$TEAM_ID/players \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "player-uuid",
    "display_name": "John Smith",
    "username": null,
    "jersey_number": "23",
    "position": "PG",
    "graduation_year": 2026,
    "status": "invited",
    "added_at": "2024-01-15T10:35:00Z"
  }
]
```

### Remove Player

```bash
PLAYER_ID="player-uuid"

curl -X DELETE http://localhost:8000/api/teams/$TEAM_ID/players/$PLAYER_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Invites

### List Invites

```bash
curl -X GET http://localhost:8000/api/invites \
  -H "Authorization: Bearer $TOKEN"
```

### Create Manual Invite (for parent)

```bash
curl -X POST http://localhost:8000/api/invites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "'$TEAM_ID'",
    "target_role": "parent",
    "target_name": "Jane Smith",
    "linked_player_id": "'$PLAYER_ID'",
    "expires_in_days": 30
  }'
```

### Preview Invite (Public, No Auth)

```bash
INVITE_CODE="abc123def456"

curl -X GET http://localhost:8000/api/invites/$INVITE_CODE
```

**Response:**
```json
{
  "code": "abc123def456",
  "team_name": "Tigers Varsity",
  "target_role": "player",
  "target_name": "John Smith",
  "expires_at": "2024-02-14T10:35:00Z",
  "is_valid": true,
  "linked_player_name": null
}
```

### Revoke Invite

```bash
INVITE_ID="invite-uuid"

curl -X DELETE http://localhost:8000/api/invites/$INVITE_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Clip Assignments

### Assign Clip to Players

```bash
CLIP_ID="clip-uuid"

curl -X POST http://localhost:8000/api/clips/$CLIP_ID/assign \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "player_ids": ["player-uuid-1", "player-uuid-2"],
    "message": "Review this defensive play",
    "priority": "high"
  }'
```

**Response:**
```json
[
  {
    "id": "assignment-uuid-1",
    "clip_id": "clip-uuid",
    "player_id": "player-uuid-1",
    "player_name": "John Smith",
    "assigned_by": "coach-uuid",
    "message": "Review this defensive play",
    "priority": "high",
    "viewed_at": null,
    "acknowledged_at": null,
    "created_at": "2024-01-15T10:40:00Z"
  },
  {
    "id": "assignment-uuid-2",
    "clip_id": "clip-uuid",
    "player_id": "player-uuid-2",
    "player_name": "Jane Doe",
    "assigned_by": "coach-uuid",
    "message": "Review this defensive play",
    "priority": "high",
    "viewed_at": null,
    "acknowledged_at": null,
    "created_at": "2024-01-15T10:40:00Z"
  }
]
```

### List Clip Assignments

```bash
curl -X GET http://localhost:8000/api/clips/$CLIP_ID/assignments \
  -H "Authorization: Bearer $TOKEN"
```

### Remove Assignment

```bash
curl -X DELETE http://localhost:8000/api/clips/$CLIP_ID/assignments/$PLAYER_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Annotations

### Get Annotations

```bash
curl -X GET http://localhost:8000/api/clips/$CLIP_ID/annotations \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "id": "annotation-uuid",
  "clip_id": "clip-uuid",
  "created_by": "coach-uuid",
  "drawing_data": {
    "objects": [
      {
        "type": "circle",
        "left": 100,
        "top": 200,
        "radius": 50,
        "stroke": "#ff0000"
      }
    ]
  },
  "audio_path": "annotations/clip-uuid/audio_uuid.webm",
  "version": 1,
  "created_at": "2024-01-15T10:45:00Z",
  "updated_at": "2024-01-15T10:45:00Z"
}
```

### Save Annotations

```bash
curl -X POST http://localhost:8000/api/clips/$CLIP_ID/annotations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "drawing_data": {
      "objects": [
        {
          "type": "arrow",
          "x1": 100,
          "y1": 200,
          "x2": 300,
          "y2": 150,
          "stroke": "#ff0000",
          "strokeWidth": 4
        }
      ]
    }
  }'
```

### Upload Audio

```bash
curl -X POST http://localhost:8000/api/clips/$CLIP_ID/audio \
  -H "Authorization: Bearer $TOKEN" \
  -F "audio=@recording.webm"
```

### Stream Audio

```bash
curl -X GET http://localhost:8000/api/clips/$CLIP_ID/audio \
  -H "Authorization: Bearer $TOKEN" \
  --output audio.webm
```

### Delete Audio

```bash
curl -X DELETE http://localhost:8000/api/clips/$CLIP_ID/audio \
  -H "Authorization: Bearer $TOKEN"
```

---

## Stats

### Add/Update Game Stats

```bash
GAME_ID="game-uuid"

curl -X POST http://localhost:8000/api/games/$GAME_ID/stats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stats": [
      {
        "player_id": "player-uuid-1",
        "points": 18,
        "field_goals_made": 7,
        "field_goals_attempted": 15,
        "three_pointers_made": 2,
        "three_pointers_attempted": 6,
        "free_throws_made": 2,
        "free_throws_attempted": 3,
        "offensive_rebounds": 3,
        "defensive_rebounds": 5,
        "assists": 4,
        "steals": 2,
        "blocks": 1,
        "turnovers": 3,
        "fouls": 2,
        "minutes_played": 32
      },
      {
        "player_id": "player-uuid-2",
        "points": 12,
        "field_goals_made": 5,
        "field_goals_attempted": 10,
        "three_pointers_made": 1,
        "three_pointers_attempted": 3,
        "free_throws_made": 1,
        "free_throws_attempted": 2,
        "offensive_rebounds": 1,
        "defensive_rebounds": 4,
        "assists": 6,
        "steals": 3,
        "blocks": 0,
        "turnovers": 2,
        "fouls": 3,
        "minutes_played": 28
      }
    ]
  }'
```

### Get Game Stats

```bash
curl -X GET http://localhost:8000/api/games/$GAME_ID/stats \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "game_id": "game-uuid",
  "game_name": "vs. Warriors",
  "stats": [
    {
      "player_id": "player-uuid-1",
      "player_name": "John Smith",
      "points": 18,
      "field_goals_made": 7,
      "field_goals_attempted": 15,
      ...
    }
  ]
}
```

### Get Player Aggregate Stats

```bash
curl -X GET http://localhost:8000/api/players/$PLAYER_ID/stats \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "player_id": "player-uuid",
  "player_name": "John Smith",
  "games_played": 5,
  "total_points": 85,
  "total_rebounds": 42,
  "total_assists": 23,
  "avg_points": 17.0,
  "avg_rebounds": 8.4,
  "avg_assists": 4.6,
  "fg_percentage": 45.2,
  "three_pt_percentage": 35.7,
  "ft_percentage": 82.5
}
```

### Get Team Stats

```bash
curl -X GET http://localhost:8000/api/teams/$TEAM_ID/stats \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "team_id": "team-uuid",
  "team_name": "Tigers Varsity",
  "total_games": 5,
  "player_stats": [
    {
      "player_id": "player-uuid-1",
      "player_name": "John Smith",
      "games_played": 5,
      "total_points": 85,
      "avg_points": 17.0,
      ...
    },
    {
      "player_id": "player-uuid-2",
      "player_name": "Jane Doe",
      "games_played": 4,
      "total_points": 48,
      "avg_points": 12.0,
      ...
    }
  ]
}
```

---

## Coach Management

### List Team Coaches

```bash
curl -X GET http://localhost:8000/api/teams/$TEAM_ID/coaches \
  -H "Authorization: Bearer $TOKEN"
```

### Add Assistant Coach

```bash
ASSISTANT_COACH_ID="other-coach-uuid"

curl -X POST http://localhost:8000/api/teams/$TEAM_ID/coaches \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "coach_id": "'$ASSISTANT_COACH_ID'",
    "role": "assistant"
  }'
```

### Remove Coach

```bash
curl -X DELETE http://localhost:8000/api/teams/$TEAM_ID/coaches/$ASSISTANT_COACH_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Error Cases to Test

### 401 Unauthorized (No Token)

```bash
curl -X GET http://localhost:8000/api/teams
# Response: {"detail": "Not authenticated"}
```

### 403 Forbidden (Wrong Team)

```bash
# Try to access another coach's team
OTHER_TEAM_ID="other-coach-team-uuid"

curl -X GET http://localhost:8000/api/teams/$OTHER_TEAM_ID \
  -H "Authorization: Bearer $TOKEN"
# Response: {"detail": "No access to this team"}
```

### 404 Not Found

```bash
curl -X GET http://localhost:8000/api/teams/00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer $TOKEN"
# Response: {"detail": "Team not found"}
```

### 400 Bad Request (Invalid Data)

```bash
curl -X POST http://localhost:8000/api/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": ""
  }'
# Response: {"detail": [{"loc": ["body", "name"], "msg": "..."}]}
```

---

## Testing Workflow

1. **Login as coach** → Get TOKEN
2. **Create team** → Get TEAM_ID
3. **Add players** → Get PLAYER_IDs and INVITE_CODEs
4. **Player claims invite** (via /auth/register endpoint)
5. **Create game** → Get GAME_ID
6. **Upload video** → Get VIDEO_ID
7. **Create clip** → Get CLIP_ID
8. **Assign clip** to players
9. **Add annotations** to clip
10. **Upload audio** for clip
11. **Enter stats** for game
12. **View aggregate stats** for player and team

---

## Postman Collection

Import these into Postman for easier testing:

1. Create environment with variables:
   - `BASE_URL`: http://localhost:8000/api
   - `TOKEN`: {{login_response.access_token}}
   - `TEAM_ID`: {{create_team_response.id}}
   - `PLAYER_ID`: {{add_player_response.player.id}}
   - `CLIP_ID`: {{create_clip_response.id}}

2. Set up collection with pre-request script:
   ```javascript
   pm.request.headers.add({
       key: 'Authorization',
       value: 'Bearer ' + pm.environment.get('TOKEN')
   });
   ```

---

## Frontend Development Server

When testing with frontend:

1. Backend runs on port 8000
2. Frontend served via nginx or python http.server
3. CORS already configured in app.py
4. Use `/api` prefix in fetch calls

---

Happy Testing!

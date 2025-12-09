# Coach Frontend Implementation Guide

Quick reference for implementing the coach dashboard in `/frontend/index.html`.

---

## Architecture Overview

The frontend is a **single-page application (SPA)** in vanilla JavaScript. No build process, no framework - just HTML/CSS/JS.

**Current Structure:**
- Auth state stored in `localStorage.getItem('token')` and `localStorage.getItem('user')`
- Role-based rendering: check `user.role` to determine which dashboard to show
- API calls use `/api` prefix (proxied by nginx to backend)

---

## Step 1: Add Role Detection

```javascript
// Check if user is authenticated
const token = localStorage.getItem('token');
const user = JSON.parse(localStorage.getItem('user') || '{}');

if (!token) {
    // Show login page
    renderLoginPage();
} else if (user.role === 'coach') {
    renderCoachDashboard();
} else if (user.role === 'player' || user.role === 'parent') {
    // Agent 3 already built this - player-parent.html
    window.location.href = '/player-parent.html';
}
```

---

## Step 2: Fetch Coach's Teams

```javascript
async function loadTeams() {
    const response = await fetch('/api/teams', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });

    if (!response.ok) {
        if (response.status === 401) {
            // Token expired, redirect to login
            localStorage.removeItem('token');
            window.location.reload();
        }
        throw new Error('Failed to load teams');
    }

    const teams = await response.json();
    return teams;
}
```

---

## Step 3: Team Management UI

### HTML Structure

```html
<div id="coach-dashboard">
    <header>
        <h1>Coach Dashboard</h1>
        <div>
            <select id="team-selector">
                <!-- Populated dynamically -->
            </select>
            <button onclick="showCreateTeamModal()">Create Team</button>
            <button onclick="logout()">Logout</button>
        </div>
    </header>

    <div id="team-content">
        <!-- Roster, clips, stats tabs -->
    </div>
</div>
```

### Create Team Modal

```javascript
function showCreateTeamModal() {
    const modal = document.getElementById('create-team-modal');
    modal.style.display = 'block';
}

async function createTeam() {
    const name = document.getElementById('team-name').value;
    const season = document.getElementById('team-season').value;

    const response = await fetch('/api/teams', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, season })
    });

    if (response.ok) {
        const team = await response.json();
        // Reload teams and select new one
        await loadTeams();
        document.getElementById('team-selector').value = team.id;
    }
}
```

---

## Step 4: Roster Management

### Fetch Roster

```javascript
async function loadRoster(teamId) {
    const response = await fetch(`/api/teams/${teamId}/players`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });

    const players = await response.json();
    renderRosterTable(players);
}
```

### Add Player (Auto-generates Invite)

```javascript
async function addPlayer(teamId) {
    const data = {
        display_name: document.getElementById('player-name').value,
        jersey_number: document.getElementById('jersey-number').value,
        position: document.getElementById('position').value,
        graduation_year: parseInt(document.getElementById('grad-year').value)
    };

    const response = await fetch(`/api/teams/${teamId}/players`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });

    if (response.ok) {
        const result = await response.json();
        // result.player = player data
        // result.invite = { code, expires_at }

        alert(`Player added! Invite code: ${result.invite.code}`);
        copyToClipboard(`${window.location.origin}/player-parent.html#/join/${result.invite.code}`);
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
}
```

### Roster Table

```html
<table id="roster-table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Jersey #</th>
            <th>Position</th>
            <th>Grad Year</th>
            <th>Status</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        <!-- Populated with renderRosterTable() -->
    </tbody>
</table>
```

---

## Step 5: Clip Assignment

### Assign Modal

```javascript
function showAssignModal(clipId) {
    document.getElementById('assign-clip-id').value = clipId;
    // Load roster for checkboxes
    loadRosterForAssignment();
    document.getElementById('assign-modal').style.display = 'block';
}

async function assignClip() {
    const clipId = document.getElementById('assign-clip-id').value;
    const checkboxes = document.querySelectorAll('.player-checkbox:checked');
    const playerIds = Array.from(checkboxes).map(cb => cb.value);
    const message = document.getElementById('assign-message').value;
    const priority = document.getElementById('assign-priority').value;

    const response = await fetch(`/api/clips/${clipId}/assign`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            player_ids: playerIds,
            message: message,
            priority: priority
        })
    });

    if (response.ok) {
        alert('Clip assigned successfully');
        document.getElementById('assign-modal').style.display = 'none';
    }
}
```

---

## Step 6: Fabric.js Annotations

### Include Library

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.0/fabric.min.js"></script>
```

### Create Canvas Overlay

```javascript
let annotationCanvas;

function initAnnotationCanvas(videoElement) {
    const canvasEl = document.getElementById('annotation-canvas');
    canvasEl.width = videoElement.videoWidth;
    canvasEl.height = videoElement.videoHeight;

    annotationCanvas = new fabric.Canvas('annotation-canvas', {
        isDrawingMode: false
    });

    // Position canvas over video
    canvasEl.style.position = 'absolute';
    canvasEl.style.top = videoElement.offsetTop + 'px';
    canvasEl.style.left = videoElement.offsetLeft + 'px';
}
```

### Drawing Tools

```javascript
function enableDrawing(tool) {
    switch(tool) {
        case 'freehand':
            annotationCanvas.isDrawingMode = true;
            annotationCanvas.freeDrawingBrush.color = currentColor;
            annotationCanvas.freeDrawingBrush.width = 3;
            break;

        case 'arrow':
            annotationCanvas.isDrawingMode = false;
            // Add arrow drawing logic
            break;

        case 'circle':
            annotationCanvas.isDrawingMode = false;
            // Add circle drawing logic
            break;
    }
}

function setDrawingColor(color) {
    currentColor = color;
    if (annotationCanvas.isDrawingMode) {
        annotationCanvas.freeDrawingBrush.color = color;
    }
}
```

### Save Annotations

```javascript
async function saveAnnotations(clipId) {
    const canvasJSON = annotationCanvas.toJSON();

    const response = await fetch(`/api/clips/${clipId}/annotations`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            drawing_data: canvasJSON
        })
    });

    if (response.ok) {
        alert('Annotations saved');
    }
}
```

### Load Annotations

```javascript
async function loadAnnotations(clipId) {
    const response = await fetch(`/api/clips/${clipId}/annotations`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });

    if (response.ok) {
        const data = await response.json();
        if (data && data.drawing_data) {
            annotationCanvas.loadFromJSON(data.drawing_data);
        }
    }
}
```

---

## Step 7: Audio Recording

### Start Recording

```javascript
let mediaRecorder;
let audioChunks = [];

async function startAudioRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        await uploadAudio(audioBlob);
        audioChunks = [];
    };

    mediaRecorder.start();

    // Start video playback simultaneously
    document.getElementById('clip-video').play();
}

function stopAudioRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        document.getElementById('clip-video').pause();
    }
}
```

### Upload Audio

```javascript
async function uploadAudio(audioBlob) {
    const clipId = document.getElementById('current-clip-id').value;
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');

    const response = await fetch(`/api/clips/${clipId}/audio`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
    });

    if (response.ok) {
        alert('Audio uploaded');
    }
}
```

---

## Step 8: Stats Entry

### Stats Form

```javascript
async function saveGameStats(gameId) {
    const playerRows = document.querySelectorAll('.stat-row');
    const stats = [];

    playerRows.forEach(row => {
        stats.push({
            player_id: row.dataset.playerId,
            points: parseInt(row.querySelector('.points').value) || 0,
            field_goals_made: parseInt(row.querySelector('.fgm').value) || 0,
            field_goals_attempted: parseInt(row.querySelector('.fga').value) || 0,
            three_pointers_made: parseInt(row.querySelector('.tpm').value) || 0,
            three_pointers_attempted: parseInt(row.querySelector('.tpa').value) || 0,
            free_throws_made: parseInt(row.querySelector('.ftm').value) || 0,
            free_throws_attempted: parseInt(row.querySelector('.fta').value) || 0,
            offensive_rebounds: parseInt(row.querySelector('.oreb').value) || 0,
            defensive_rebounds: parseInt(row.querySelector('.dreb').value) || 0,
            assists: parseInt(row.querySelector('.ast').value) || 0,
            steals: parseInt(row.querySelector('.stl').value) || 0,
            blocks: parseInt(row.querySelector('.blk').value) || 0,
            turnovers: parseInt(row.querySelector('.tov').value) || 0,
            fouls: parseInt(row.querySelector('.pf').value) || 0,
            minutes_played: parseInt(row.querySelector('.min').value) || null
        });
    });

    const response = await fetch(`/api/games/${gameId}/stats`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ stats })
    });

    if (response.ok) {
        alert('Stats saved');
    }
}
```

---

## UI Components Checklist

- [ ] Team selector dropdown
- [ ] Create/edit team modal
- [ ] Roster table with add/remove
- [ ] Invite code display with copy button
- [ ] Clip assignment modal with player checkboxes
- [ ] Annotation canvas overlay with tools
- [ ] Color picker for annotations
- [ ] Audio recording controls
- [ ] Stats entry form
- [ ] Team stats summary view

---

## Styling Tips

1. **Match existing theme**: Use CSS variables from existing index.html
2. **Mobile responsive**: Use flexbox/grid, test on mobile
3. **Modals**: Use overlay with z-index, close on click outside
4. **Tables**: Zebra striping, hover effects
5. **Forms**: Label alignment, validation feedback

---

## Error Handling

```javascript
async function apiCall(url, options) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                ...options.headers
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Token expired
                localStorage.removeItem('token');
                window.location.reload();
                return;
            }

            const error = await response.json();
            throw new Error(error.detail || 'API error');
        }

        return await response.json();
    } catch (err) {
        alert('Error: ' + err.message);
        console.error(err);
    }
}
```

---

## Quick Start

1. Add coach dashboard div to index.html
2. Implement team selector
3. Build roster table
4. Add clip assignment modal
5. Integrate Fabric.js
6. Add audio recording
7. Build stats form
8. Test all flows

Good luck! The backend is ready and waiting.

// ===== TEAMS MANAGEMENT =====

// Load teams list
async function loadCoachTeams() {
    const container = document.getElementById('coachTeamsContainer');

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams`);
        if (!response.ok) {
            throw new Error('Failed to load teams');
        }

        const teams = await response.json();

        if (teams.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 40px;">No teams yet. Create your first team to get started!</p>';
            return;
        }

        // Get player counts for each team
        const teamsWithCounts = await Promise.all(teams.map(async (team) => {
            try {
                const playersResponse = await authenticatedFetch(`${API_BASE}/teams/${team.id}/players`);
                const players = await playersResponse.json();
                return { ...team, playerCount: players.length };
            } catch {
                return { ...team, playerCount: 0 };
            }
        }));

        container.innerHTML = `
            <div class="game-list">
                ${teamsWithCounts.map(team => `
                    <div class="game-item" style="cursor: pointer;" onclick="showTeamDetail('${team.id}')">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div style="flex: 1;">
                                <h3 style="margin: 0 0 8px 0; color: var(--text-primary);">${team.name}</h3>
                                ${team.season ? `<p style="margin: 0 0 8px 0; color: var(--text-secondary); font-size: 14px;">Season: ${team.season}</p>` : ''}
                                <p style="margin: 0; color: var(--text-tertiary); font-size: 13px;">${team.playerCount} player${team.playerCount !== 1 ? 's' : ''}</p>
                            </div>
                            <div style="display: flex; gap: 8px;">
                                <button onclick="event.stopPropagation(); showEditTeamModal('${team.id}', '${team.name.replace(/'/g, "\\'")}', '${team.season || ''}')" style="padding: 8px 16px; background: #3498db;">Edit</button>
                                <button onclick="event.stopPropagation(); deleteTeam('${team.id}', '${team.name.replace(/'/g, "\\'")}');" style="padding: 8px 16px; background: #e74c3c;">Delete</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (error) {
        console.error('Error loading teams:', error);
        container.innerHTML = '<p style="color: #e74c3c;">Error loading teams. Please try again.</p>';
    }
}

// Show create team modal
function showCreateTeamModal() {
    document.getElementById('teamName').value = '';
    document.getElementById('teamSeason').value = '';
    document.getElementById('createTeamModal').style.display = 'block';
}

// Close create team modal
function closeCreateTeamModal() {
    document.getElementById('createTeamModal').style.display = 'none';
}

// Handle create team form submission
async function handleCreateTeam(event) {
    event.preventDefault();

    const name = document.getElementById('teamName').value;
    const season = document.getElementById('teamSeason').value;

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, season })
        });

        if (!response.ok) {
            throw new Error('Failed to create team');
        }

        closeCreateTeamModal();
        loadCoachTeams();
        alert('Team created successfully!');
    } catch (error) {
        console.error('Error creating team:', error);
        alert('Failed to create team. Please try again.');
    }
}

// Show edit team modal
function showEditTeamModal(teamId, teamName, teamSeason) {
    document.getElementById('editTeamId').value = teamId;
    document.getElementById('editTeamName').value = teamName;
    document.getElementById('editTeamSeason').value = teamSeason;
    document.getElementById('editTeamModal').style.display = 'block';
}

// Close edit team modal
function closeEditTeamModal() {
    document.getElementById('editTeamModal').style.display = 'none';
}

// Handle edit team form submission
async function handleEditTeam(event) {
    event.preventDefault();

    const teamId = document.getElementById('editTeamId').value;
    const name = document.getElementById('editTeamName').value;
    const season = document.getElementById('editTeamSeason').value;

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams/${teamId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, season })
        });

        if (!response.ok) {
            throw new Error('Failed to update team');
        }

        closeEditTeamModal();
        loadCoachTeams();
        alert('Team updated successfully!');
    } catch (error) {
        console.error('Error updating team:', error);
        alert('Failed to update team. Please try again.');
    }
}

// Delete team
async function deleteTeam(teamId, teamName) {
    if (!confirm(`Are you sure you want to delete "${teamName}"? This will remove all associated data.`)) {
        return;
    }

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams/${teamId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete team');
        }

        loadCoachTeams();
        alert('Team deleted successfully!');
    } catch (error) {
        console.error('Error deleting team:', error);
        alert('Failed to delete team. Please try again.');
    }
}

// Show team detail modal
async function showTeamDetail(teamId) {
    document.getElementById('teamDetailModal').style.display = 'block';

    try {
        // Load team info
        const teamResponse = await authenticatedFetch(`${API_BASE}/teams/${teamId}`);
        if (!teamResponse.ok) throw new Error('Failed to load team');
        const team = await teamResponse.json();

        // Load roster
        const playersResponse = await authenticatedFetch(`${API_BASE}/teams/${teamId}/players`);
        if (!playersResponse.ok) throw new Error('Failed to load roster');
        const players = await playersResponse.json();

        // Load coaches
        const coachesResponse = await authenticatedFetch(`${API_BASE}/teams/${teamId}/coaches`);
        if (!coachesResponse.ok) throw new Error('Failed to load coaches');
        const coaches = await coachesResponse.json();

        document.getElementById('teamDetailTitle').textContent = team.name;

        document.getElementById('teamDetailContent').innerHTML = `
            <div style="margin-bottom: 30px;">
                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 8px 0;">Team Information</h3>
                    ${team.season ? `<p style="margin: 0; color: var(--text-secondary);">Season: ${team.season}</p>` : ''}
                </div>

                <div style="margin-bottom: 30px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <h3 style="margin: 0;">Roster (${players.length})</h3>
                        <button onclick="showAddPlayerModal('${teamId}')" style="background: #27ae60; padding: 8px 16px;">+ Add Player</button>
                    </div>
                    ${players.length === 0 ? '<p style="color: var(--text-secondary); text-align: center; padding: 20px;">No players on roster yet.</p>' : `
                        <table class="data-table">
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
                                ${players.map(player => `
                                    <tr>
                                        <td><strong>${player.display_name}</strong></td>
                                        <td>${player.jersey_number || '-'}</td>
                                        <td>${player.position || '-'}</td>
                                        <td>${player.graduation_year || '-'}</td>
                                        <td>
                                            <span style="padding: 4px 8px; border-radius: 4px; font-size: 12px; ${player.status === 'active' ? 'background: #d4edda; color: #155724;' : 'background: #fff3cd; color: #856404;'}">
                                                ${player.status}
                                            </span>
                                        </td>
                                        <td>
                                            <button onclick="removePlayer('${teamId}', '${player.id}', '${player.display_name.replace(/'/g, "\\'")}');" style="padding: 6px 12px; background: #e74c3c; font-size: 13px;">Remove</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>

                <div style="margin-bottom: 30px;">
                    <h3 style="margin: 0 0 15px 0;">Coaching Staff (${coaches.length})</h3>
                    ${coaches.length === 0 ? '<p style="color: var(--text-secondary);">No coaches assigned.</p>' : `
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Role</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${coaches.map(coach => `
                                    <tr>
                                        <td><strong>${coach.display_name}</strong></td>
                                        <td>${coach.email || '-'}</td>
                                        <td style="text-transform: capitalize;">${coach.role}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>

                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <h3 style="margin: 0;">Team Invites</h3>
                        <button onclick="showCreateInviteModal('${teamId}')" style="background: #9b59b6; padding: 8px 16px;">+ Create Invite</button>
                    </div>
                    <div id="teamInvitesContainer">
                        <p style="color: var(--text-secondary); font-style: italic;">Loading invites...</p>
                    </div>
                </div>
            </div>
        `;

        // Load invites for this team
        if (typeof loadTeamInvites === 'function') {
            loadTeamInvites(teamId);
        }
    } catch (error) {
        console.error('Error loading team details:', error);
        document.getElementById('teamDetailContent').innerHTML = '<p style="color: #e74c3c;">Error loading team details. Please try again.</p>';
    }
}

// Close team detail modal
function closeTeamDetailModal() {
    document.getElementById('teamDetailModal').style.display = 'none';
}

// Show add player modal
function showAddPlayerModal(teamId) {
    document.getElementById('addPlayerTeamId').value = teamId;
    document.getElementById('playerName').value = '';
    document.getElementById('playerJersey').value = '';
    document.getElementById('playerPosition').value = '';
    document.getElementById('playerGradYear').value = '';
    document.getElementById('addPlayerInviteCode').style.display = 'none';
    document.getElementById('addPlayerModal').style.display = 'block';
}

// Close add player modal
function closeAddPlayerModal() {
    document.getElementById('addPlayerModal').style.display = 'none';
}

// Handle add player form submission
async function handleAddPlayer(event) {
    event.preventDefault();

    const teamId = document.getElementById('addPlayerTeamId').value;
    const displayName = document.getElementById('playerName').value;
    const jerseyNumber = document.getElementById('playerJersey').value;
    const position = document.getElementById('playerPosition').value;
    const graduationYear = document.getElementById('playerGradYear').value;

    const payload = { display_name: displayName };
    if (jerseyNumber) payload.jersey_number = jerseyNumber;
    if (position) payload.position = position;
    if (graduationYear) payload.graduation_year = parseInt(graduationYear);

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams/${teamId}/players`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error('Failed to add player');
        }

        const result = await response.json();

        // Show invite code
        document.getElementById('inviteCodeDisplay').value = result.invite.code;
        document.getElementById('addPlayerInviteCode').style.display = 'block';

        // Refresh team detail if it's open
        showTeamDetail(teamId);
    } catch (error) {
        console.error('Error adding player:', error);
        alert('Failed to add player. Please try again.');
    }
}

// Copy invite code to clipboard
function copyInviteCode() {
    const input = document.getElementById('inviteCodeDisplay');
    input.select();
    document.execCommand('copy');
    alert('Invite code copied to clipboard!');
}

// Remove player from roster
async function removePlayer(teamId, playerId, playerName) {
    if (!confirm(`Remove ${playerName} from the roster?`)) {
        return;
    }

    try {
        const response = await authenticatedFetch(`${API_BASE}/teams/${teamId}/players/${playerId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to remove player');
        }

        showTeamDetail(teamId);
        alert('Player removed from roster successfully!');
    } catch (error) {
        console.error('Error removing player:', error);
        alert('Failed to remove player. Please try again.');
    }
}

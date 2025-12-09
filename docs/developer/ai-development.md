# AI-Assisted Development Guide

This guide documents how to effectively use Claude Code and sub-agents for development on this project.

## Agent Architecture

This project was developed using a multi-agent architecture with 7 specialized Claude agents:

| Agent | Responsibility | Key Artifacts |
|-------|---------------|---------------|
| Foundation | Authentication, database schema, core infrastructure | `backend/auth/`, `migrations/` |
| Coach Side | Team management, invites, assignments, annotations | `backend/routes/teams.py`, `assignments.py`, `annotations.py` |
| Player Side | Player portal, parent portal, clip viewing | `frontend/player-parent.html`, `backend/routes/player.py` |
| Testing | Unit, integration, and security tests | `tests/` |
| Security | Rate limiting, headers, audit logging, vulnerability review | `backend/middleware/`, `SECURITY_AUDIT.md` |
| DevOps | CI/CD, migrations, Helm/Flux configuration | `.github/workflows/`, `helm/`, `flux/` |
| Documentation | User guides, API docs, developer docs, operations | `docs/` |

## Shared Context: SPEC.md

All agents share context through `SPEC.md` at the project root. This file contains:

- Database schema
- API conventions (auth headers, error formats, pagination)
- Authentication patterns (JWT structure, token refresh)
- Data formats (annotations JSON structure)
- Security requirements

**When modifying the system**, update SPEC.md first so all agents have consistent context.

## Re-engaging Agents for Iteration

When continuing development on features originally built by an agent, follow these patterns:

### 1. Provide SPEC.md Context

Always include SPEC.md content when re-engaging for related work:

```
Read SPEC.md and the following files, then [your task]:
- backend/routes/teams.py
- tests/integration/test_teams_api.py
```

### 2. Reference Original Agent Scope

Specify which agent's domain you're working in:

```
Working on the Coach Side domain (teams, invites, assignments).
The Testing agent will need to add tests for this change.
```

### 3. Sequential Agent Re-engagement

For changes that span multiple agents, engage them in order:

1. **Foundation** first (if changing schema or auth)
2. **Feature agents** (Coach Side, Player Side)
3. **Testing** (add tests for changes)
4. **Security** (review new endpoints)
5. **DevOps** (if deployment changes needed)
6. **Documentation** (update user/API docs)

### 4. Example Re-engagement Prompt

```
I need to add a "archive team" feature. This involves:

Context files to read:
- SPEC.md (shared context)
- backend/routes/teams.py (existing team routes)
- tests/integration/test_teams_api.py (existing tests)

Changes needed:
1. Add archive_team endpoint (Coach Side agent domain)
2. Add tests (Testing agent domain)
3. Document in API docs (Documentation agent domain)

Please implement the archive_team endpoint, then I'll run the Testing agent
to add tests, then Documentation agent to update docs.
```

## CI/CD Integration

### Test Gating

Tests gate deployment in `.github/workflows/build-and-push.yml`:

```yaml
determine-version:
  needs: test  # Only runs if tests pass
```

If tests fail:
- Builds do not run
- No images are pushed
- No deployment occurs

### Workflow Separation

- `test.yml` - Runs on PRs and develop branch (fast feedback)
- `build-and-push.yml` - Runs on main branch (gates deployment)

### Adding Tests for New Features

When a feature agent adds code, the Testing agent should:

1. Add unit tests for pure functions
2. Add integration tests for API endpoints
3. Add security tests for access control

Example test structure:
```python
# tests/integration/test_new_feature.py
@pytest.mark.asyncio
async def test_feature_happy_path(async_client, auth_token):
    """Test normal operation"""
    response = await async_client.post(...)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_feature_unauthorized(async_client):
    """Test without auth"""
    response = await async_client.post(...)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_feature_wrong_role(async_client, player_token):
    """Test with wrong role"""
    response = await async_client.post(...)
    assert response.status_code == 403
```

## Integration Testing Coverage

### What Can Be Integration Tested

| Area | Coverage | Method |
|------|----------|--------|
| API Endpoints | Full | httpx AsyncClient against FastAPI TestClient |
| Authentication | Full | JWT token generation/validation |
| Authorization | Full | Role checks, data isolation |
| Database Operations | Full | Test PostgreSQL service in CI |
| MinIO Operations | Partial | MinIO service in CI, mock for speed |
| Video Processing | Mock | ffmpeg is slow, mock for CI |
| Kubernetes | None | Use staging environment |

### Running Integration Tests Locally

```bash
# Start services
docker-compose up -d postgres minio

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=backend
```

### CI Test Environment

GitHub Actions provides:
- PostgreSQL 15 service container
- MinIO service container (test.yml only)
- Python 3.11
- All test dependencies

## Security Testing

Security tests in `tests/security/` verify:

1. **Data isolation** - Player A cannot see Player B's data
2. **Role enforcement** - Coaches have coach access, players have player access
3. **Input validation** - SQL injection, XSS prevention
4. **Rate limiting** - Auth endpoints have stricter limits

Example security test:
```python
@pytest.mark.asyncio
async def test_player_cannot_access_other_players_clips(
    async_client, player_a_token, player_b_clip_id
):
    """Verify data isolation between players"""
    response = await async_client.get(
        f"/clips/{player_b_clip_id}",
        headers={"Authorization": f"Bearer {player_a_token}"}
    )
    # Should not find clip (403) or return empty (depends on implementation)
    assert response.status_code in [403, 404]
```

## DevOps Agent Updates

When making infrastructure changes:

### Secrets Management (1Password)

The cluster uses the **1Password Operator** for secrets. Never hardcode secrets in Helm values or commit them to Git.

**To add a new secret:**
1. Add the field to the 1Password item (`vaults/Kubernetes/items/basketball-film-review`)
2. Reference it in the deployment via `secretKeyRef`:
   ```yaml
   env:
     - name: NEW_SECRET
       valueFrom:
         secretKeyRef:
           name: basketball-film-review-secrets
           key: NEW_SECRET
   ```

See SPEC.md "Secrets Management (1Password)" section for full details.

### Helm Chart Changes

1. Update `helm/values.yaml` for new configuration
2. Update templates in `helm/templates/` for new resources
3. Test with `helm template ./helm` before committing
4. Flux will auto-deploy changes

### CI/CD Changes

1. Modify `.github/workflows/build-and-push.yml` for build changes
2. Modify `.github/workflows/test.yml` for PR/develop testing
3. Test workflow changes in a branch first

### Migration Changes

1. Add SQL to `migrations/` directory
2. Update `backend/migrate.py` if needed
3. Run migrations before deploying code that uses new schema

## Documentation Agent Updates

When adding features:

1. **API docs** (`docs/api/endpoints.md`) - New endpoints
2. **User guides** (`docs/user-guide/`) - User-facing features
3. **Developer guide** (`docs/developer/README.md`) - Technical details
4. **Operations guide** (`docs/operations/README.md`) - Deployment/monitoring

## Troubleshooting Agent Issues

### Agent Lost Context

If an agent seems to have lost context about the project:
1. Point it to SPEC.md
2. Have it read the relevant source files
3. Reference previous agent outputs

### Agent Making Conflicting Changes

If agents make conflicting changes:
1. Establish clear boundaries (see agent table above)
2. Use SPEC.md as source of truth
3. Run Testing agent after each change to catch conflicts

### Agent Not Following Patterns

If an agent deviates from project patterns:
1. Point to existing code as examples
2. Reference SPEC.md conventions
3. Show test expectations

## Best Practices

1. **Always update SPEC.md first** for schema/API changes
2. **Run tests after each agent's changes** before moving to next agent
3. **Use conventional commits** for proper versioning
4. **Document as you go** - Don't leave documentation for last
5. **Security review new endpoints** before merging to main

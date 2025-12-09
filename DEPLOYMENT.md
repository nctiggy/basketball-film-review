# Deployment Guide - Basketball Film Review

This guide covers deploying the enhanced Basketball Film Review application with authentication, teams, and player features.

## Prerequisites

- Kubernetes cluster with kubectl configured
- Helm 3.x installed
- Docker registry access (Docker Hub: nctiggy)
- PostgreSQL database (standalone or via Helm)
- MinIO object storage (standalone or via Helm)

## Quick Start

### 1. Configure Authentication Secrets

```bash
# Copy the example auth values file
cp helm/values-auth-example.yaml helm/values-auth.yaml

# Generate a strong JWT secret
openssl rand -base64 32

# Edit helm/values-auth.yaml and add:
# - Your generated JWT secret
# - Google OAuth credentials (optional)
```

**IMPORTANT**: Never commit `helm/values-auth.yaml` to git! It's already in `.gitignore`.

### 2. Deploy to Kubernetes

```bash
# Set your kubeconfig
export KUBECONFIG=path/to/your/kubeconfig

# Deploy with Helm
helm upgrade --install basketball-film-review ./helm \
  -f helm/values.yaml \
  -f helm/values-auth.yaml \
  --namespace film-review \
  --create-namespace

# Check deployment status
kubectl get pods -n film-review
kubectl logs -n film-review -l component=backend -f
```

### 3. Verify Migration

The init container will automatically run database migrations. Check the logs:

```bash
# View migration logs
kubectl logs -n film-review <backend-pod-name> -c migrate

# Should show output like:
# Applied migrations: 0
# Found 1 migration files
# Pending migrations: 1
#   - 001: add users teams auth
# SUCCESS: Applied 1 migrations
```

## Architecture Overview

### Components

1. **Backend** (FastAPI)
   - Handles API requests
   - Auth module (JWT, OAuth, password hashing)
   - Route modules (teams, players, clips, stats, etc.)
   - Database migrations via init container

2. **Frontend** (Nginx + Vanilla JS)
   - Coach dashboard: `/` (index.html)
   - Player/Parent portal: `/player` (player-parent.html)
   - Static file serving with no caching for HTML

3. **Database** (PostgreSQL)
   - Stores all metadata (users, teams, clips, stats)
   - Migrations tracked in `schema_migrations` table

4. **Storage** (MinIO)
   - Video files and audio annotations
   - S3-compatible API

### New Tables (Migration 001)

- `users` - Unified user table (coaches, players, parents)
- `teams` - Team information
- `team_coaches` - Coach assignments to teams
- `team_players` - Player roster
- `invites` - Invite codes for player/parent onboarding
- `clip_assignments` - Which clips are assigned to which players
- `clip_annotations` - Drawing and audio annotations
- `player_game_stats` - Individual player statistics
- `parent_links` - Parent-child relationships
- `refresh_tokens` - JWT refresh token tracking
- `notifications` - Notification system (future)
- `notification_preferences` - User notification settings (future)

## Migration System

### How It Works

1. **Init Container**: Runs before the backend starts
2. **Migration Script**: `backend/migrate.py` - Python script
3. **Tracking**: `schema_migrations` table tracks applied migrations
4. **Idempotent**: Safe to run multiple times
5. **ConfigMap**: Migration SQL files stored in `migrations-configmap`

### Manual Migration

If you need to run migrations manually:

```bash
# Enter backend pod
kubectl exec -it -n film-review <backend-pod> -- bash

# Run migrations
python migrate.py

# Dry run (see what would be applied)
python migrate.py --dry-run

# Reset tracking (DANGER!)
python migrate.py --reset
```

### Adding New Migrations

1. Create migration file: `migrations/002_your_description.sql`
2. Copy to helm: `helm/migrations/002_your_description.sql`
3. Update ConfigMap: `helm/templates/migrations-configmap.yaml`
4. Deploy: Migrations run automatically on next deployment

## CI/CD Pipeline

The automated pipeline runs on every push to `main`:

### Workflow Steps

1. **Test Stage** (NEW)
   - Runs pytest test suite
   - Requires PostgreSQL service
   - Must pass before building

2. **Security Scan Stage** (NEW)
   - Runs Bandit security scanner
   - Uploads report as artifact
   - Continues on error (warnings only)

3. **Determine Version**
   - Semantic versioning from commit messages
   - `feat:` → minor bump
   - `fix:` → patch bump
   - `BREAKING CHANGE:` → major bump

4. **Build Images**
   - Backend and frontend images
   - Multi-arch build (linux/amd64)
   - Push to Docker Hub

5. **Update Helm Values**
   - Auto-update image tags in `helm/values.yaml`
   - Commit and push changes
   - Create git tag

6. **Flux CD Deploys**
   - Watches git repo for changes
   - Automatically deploys to Kubernetes
   - Rollout monitoring

### Monitoring CI/CD

```bash
# View GitHub Actions
# Go to: https://github.com/your-org/basketball-film-review/actions

# View Flux status
flux get all -A
flux get helmrelease -n film-review

# View deployment logs
kubectl logs -n flux-system deployment/helm-controller -f
```

## Configuration

### Environment Variables (Backend)

Set via Helm values and secrets:

```yaml
# Database
DATABASE_URL: postgresql://user:pass@host:5432/db

# MinIO
MINIO_ENDPOINT: minio:9000
MINIO_ACCESS_KEY: minioadmin
MINIO_SECRET_KEY: minioadmin
MINIO_SECURE: "false"

# Auth (from secret)
JWT_SECRET: your-secret-key
GOOGLE_CLIENT_ID: your-client-id
GOOGLE_CLIENT_SECRET: your-client-secret
```

### Helm Values Structure

```yaml
# Backend configuration
backend:
  replicaCount: 1
  image:
    repository: nctiggy/basketball-film-review-backend
    tag: 1.10.0
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi

# Frontend configuration
frontend:
  replicaCount: 1
  image:
    repository: nctiggy/basketball-film-review-frontend
    tag: 1.10.0

# Auth configuration (from values-auth.yaml)
auth:
  jwtSecret: "your-secret"
  googleClientId: "your-client-id"
  googleClientSecret: "your-client-secret"
```

## Troubleshooting

### Migration Fails

```bash
# Check init container logs
kubectl logs -n film-review <backend-pod> -c migrate

# Common issues:
# 1. Database not ready - increase init delay
# 2. Migration syntax error - check SQL file
# 3. Already applied - check schema_migrations table

# Connect to database
kubectl exec -it -n film-review <postgres-pod> -- psql -U filmreview -d filmreview

# Check applied migrations
SELECT * FROM schema_migrations;
```

### Backend Won't Start

```bash
# Check backend logs
kubectl logs -n film-review <backend-pod> -c backend

# Common issues:
# 1. Missing JWT_SECRET - check auth secret
# 2. Database connection - check DATABASE_URL
# 3. MinIO connection - check MINIO_ENDPOINT
```

### Tests Fail in CI

```bash
# Run tests locally
docker-compose -f docker-compose.test.yml up

# Or with pytest directly
pytest tests/ -v

# Check test requirements
pip install -r backend/requirements.txt
pip install pytest pytest-asyncio httpx
```

### Frontend Not Loading

```bash
# Check frontend logs
kubectl logs -n film-review <frontend-pod>

# Check nginx config
kubectl exec -it -n film-review <frontend-pod> -- cat /etc/nginx/conf.d/default.conf

# Common issues:
# 1. player-parent.html missing - check Dockerfile COPY
# 2. API proxy failing - check backend service
```

## Security Considerations

### Secrets Management

1. **Never commit secrets to git**
   - `values-auth.yaml` is in `.gitignore`
   - Use external secrets manager in production

2. **JWT Secret**
   - Must be at least 32 characters
   - Generate with: `openssl rand -base64 32`
   - Rotate periodically

3. **Google OAuth**
   - Restrict authorized redirect URIs
   - Keep client secret secure
   - Monitor usage in Google Console

### Access Control

- **Coaches**: Full access to their teams
- **Players**: Only assigned clips and own stats
- **Parents**: Only linked children's data

All endpoints enforce role-based access control (RBAC).

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL
kubectl exec -n film-review <postgres-pod> -- \
  pg_dump -U filmreview filmreview > backup.sql

# Restore
kubectl exec -i -n film-review <postgres-pod> -- \
  psql -U filmreview filmreview < backup.sql
```

### MinIO Backup

```bash
# Use MinIO client
mc alias set myminio https://minio.example.com access-key secret-key
mc mirror myminio/basketball-clips ./backup/
```

## Scaling

### Horizontal Scaling

```bash
# Scale backend
kubectl scale deployment -n film-review basketball-film-review-backend --replicas=3

# Scale frontend
kubectl scale deployment -n film-review basketball-film-review-frontend --replicas=2
```

### Vertical Scaling

Edit `helm/values.yaml`:

```yaml
backend:
  resources:
    limits:
      cpu: 2000m      # Increase for video processing
      memory: 4Gi     # Increase for large videos
```

## Monitoring

### Health Checks

```bash
# Backend health
curl http://backend-service:8000/health

# Check pod status
kubectl get pods -n film-review -w
```

### Logs

```bash
# Backend logs
kubectl logs -n film-review -l component=backend -f --tail=100

# Frontend logs
kubectl logs -n film-review -l component=frontend -f --tail=100

# All logs
kubectl logs -n film-review --all-containers=true -f
```

## Next Steps

1. **Configure Google OAuth** (optional)
   - Create OAuth credentials in Google Console
   - Add to `values-auth.yaml`

2. **Set up monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Alert rules

3. **Configure backups**
   - Automated PostgreSQL backups
   - MinIO replication
   - Disaster recovery plan

4. **Documentation**
   - User guides (Agent 7)
   - API documentation
   - Operations runbook

## Support

For issues or questions:
- Check logs: `kubectl logs -n film-review <pod-name>`
- Review SPEC.md for architecture details
- Check CLAUDE.md for development guidelines
- Review SECURITY_AUDIT.md for security info

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: CI/CD Workflow (Automated!)

**GOOD NEWS**: Most of the build/deploy process is now automated with GitHub Actions and Flux CD!

### The New Workflow (Mostly Automated)

1. **Make your code changes** to backend or frontend
2. **Commit with conventional commit messages**:
   - `feat:` for new features → Minor version bump (1.0.0 → 1.1.0)
   - `fix:` for bug fixes → Patch version bump (1.0.0 → 1.0.1)
   - `BREAKING CHANGE:` or `feat!:` → Major version bump (1.0.0 → 2.0.0)
3. **Push to main branch** - that's it!

### What Happens Automatically

```
Your Push → GitHub Actions → Flux CD → Deployed!
```

**GitHub Actions** (.github/workflows/build-and-push.yml):
- ✅ Detects which components changed (backend/frontend)
- ✅ Determines semantic version from commit messages
- ✅ Builds with `docker buildx --platform linux/amd64`
- ✅ Updates footer version in frontend
- ✅ Pushes images to Docker Hub
- ✅ Updates `helm/values.yaml` with new image tags
- ✅ Commits changes back to Git
- ✅ Creates Git tag (e.g., v1.0.9)

**Flux CD** (flux/):
- ✅ Watches Git repo for Helm chart changes
- ✅ Watches Docker Hub for new images
- ✅ Automatically deploys to Kubernetes
- ✅ Monitors rollout status
- ✅ Retries on failure

### Manual Steps (Only if needed)

#### If CI/CD is not set up yet:
1. **Configure GitHub Secrets** (one-time setup):
   - Go to repository Settings → Secrets and variables → Actions
   - Add `DOCKER_USERNAME`: nctiggy
   - Add `DOCKER_PASSWORD`: Your Docker Hub token

2. **Configure Flux Git Push** (one-time setup):
   ```bash
   # Create GitHub Personal Access Token with 'repo' scope
   export GITHUB_TOKEN=<your-pat>
   export KUBECONFIG=admin.app-eng.kubeconfig

   kubectl create secret generic flux-system \
     --namespace=flux-system \
     --from-literal=username=git \
     --from-literal=password=${GITHUB_TOKEN}
   ```

#### If you need to deploy manually (CI/CD bypassed):
```bash
export KUBECONFIG=admin.app-eng.kubeconfig

# Suspend Flux (prevent conflicts)
flux suspend helmrelease basketball-film-review -n film-review

# Deploy manually
helm upgrade basketball-film-review ./helm -n film-review

# Resume Flux
flux resume helmrelease basketball-film-review -n film-review
```

### Monitoring the Pipeline

```bash
export KUBECONFIG=admin.app-eng.kubeconfig

# Check Flux status
flux get all -A

# Check HelmRelease
flux get helmrelease -n film-review

# Check image automation
flux get image repository -A
flux get image policy -A

# View logs
kubectl logs -n flux-system deployment/helm-controller -f
```

### OLD MANUAL WORKFLOW (Deprecated - use only if CI/CD is broken)

<details>
<summary>Click to expand manual workflow</summary>

#### 1. Update Version Footer (if frontend changes)
If you modified `frontend/index.html`, update the version in the footer:
- Find the footer version number (search for "Version")
- Increment using semantic versioning: MAJOR.MINOR.PATCH

#### 2. Build Images with Buildx for AMD64
```bash
export IMAGE_REGISTRY="nctiggy"
export IMAGE_TAG="1.0.X"

docker buildx build --platform linux/amd64 \
  -t ${IMAGE_REGISTRY}/basketball-film-review-backend:${IMAGE_TAG} \
  -f backend/Dockerfile backend/ --push

docker buildx build --platform linux/amd64 \
  -t ${IMAGE_REGISTRY}/basketball-film-review-frontend:${IMAGE_TAG} \
  -f frontend/Dockerfile frontend/ --push
```

#### 3. Update Helm Values
Edit `helm/values.yaml` and update the image tags

#### 4. Deploy to Kubernetes
```bash
export KUBECONFIG=admin.app-eng.kubeconfig
helm upgrade basketball-film-review ./helm --namespace film-review
```

#### 5. Commit Changes to Git
```bash
git add .
git commit -m "Descriptive message

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```
</details>

## Project Overview

Basketball Film Review is a web application for coaches to upload game videos, create timestamped clips, and organize them with tags for film study sessions. The system processes video clips asynchronously using ffmpeg and stores everything in MinIO object storage.

## Architecture

### Stack Components
- **Backend**: Python FastAPI (backend/app.py) - single monolithic file handling all API endpoints
- **Frontend**: Vanilla HTML/CSS/JavaScript (frontend/index.html) - single-page application, no framework
- **Database**: PostgreSQL with asyncpg driver - stores game/video/clip metadata
- **Storage**: MinIO S3-compatible object storage - stores actual video files
- **Video Processing**: ffmpeg - runs in backend container for clip extraction

### Data Model
Three main tables with cascading deletes:
- `games` - game metadata (name, date)
- `videos` - uploaded full game videos (links to game, stores MinIO path)
- `clips` - extracted clips (links to game and video, stores start/end times, tags, processing status)

### Video Architecture
- Videos are uploaded to MinIO at path `games/{game_id}/{video_id}_{filename}`
- Clips are extracted to `clips/{clip_id}.mp4`
- Backend streams videos with HTTP Range request support for seeking/scrubbing
- Two MinIO endpoints: internal (minio:9000) for backend, external (localhost:9000 or LoadBalancer) for browser access

### Clip Processing Flow
1. User creates clip via POST /clips with timestamps (mm:ss or hh:mm:ss format)
2. Clip record created with status='pending'
3. Background task downloads video from MinIO, runs ffmpeg extraction, uploads clip back to MinIO
4. Status updates: pending → processing → completed (or failed)
5. Frontend polls every 10 seconds to update clip status

## Common Development Commands

### Local Development (Docker Compose)
```bash
# Start all services (postgres, minio, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f
docker-compose logs -f backend    # Backend only
docker-compose logs -f frontend   # Frontend only

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Access services
# - Frontend: http://localhost:8080
# - Backend API: http://localhost:8000
# - API docs: http://localhost:8000/docs
# - MinIO console: http://localhost:9001 (minioadmin/minioadmin)

# Database access
docker-compose exec postgres psql -U filmreview -d filmreview
```

### Building for Kubernetes
```bash
# Build and optionally push images
export IMAGE_REGISTRY="your-registry"
export IMAGE_TAG="v1.0.0"
./build.sh

# Update helm dependencies (PostgreSQL and MinIO charts)
cd helm
helm dependency update
cd ..
```

### Kubernetes Deployment
```bash
# Deploy with custom values
helm install basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review \
  --create-namespace

# Check status
kubectl get pods -n film-review

# View logs
kubectl logs -n film-review -l component=backend -f
kubectl logs -n film-review -l component=frontend -f

# Upgrade deployment
helm upgrade basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review

# Uninstall
helm uninstall basketball-film-review -n film-review
```

## Key Implementation Details

### Backend (backend/app.py)
- Single file FastAPI application (~650 lines)
- Uses asyncpg connection pool for database operations (global `db_pool`)
- MinIO client instantiated per-request via `get_minio_client()`
- Background clip processing uses FastAPI `BackgroundTasks`
- All IDs are UUIDs stored as PostgreSQL UUID type, converted to strings in JSON responses
- Video streaming supports HTTP Range requests for seeking (see `stream_video_with_range()`)

### Frontend (frontend/index.html)
- Single HTML file (~1000+ lines) with embedded CSS and JavaScript
- No build process or dependencies - served directly via nginx
- API calls use vanilla fetch() to backend at `/api` (proxied by nginx)
- Auto-refreshes clip list every 10 seconds to show processing status
- Interactive video modal for clip creation with inline player
- Tag autocomplete from previously used tags
- Quick-select buttons for top 5 most frequent tags

### Database Schema
All tables created in `lifespan()` startup event in backend/app.py:
- Games, videos, and clips tables with UUID primary keys
- Cascading deletes: deleting game deletes its videos and clips
- Clip tags stored as PostgreSQL TEXT[] array type
- Clip status: 'pending' | 'processing' | 'completed' | 'failed'

### Configuration
Backend environment variables (set in docker-compose.yml or Kubernetes secrets):
- `DATABASE_URL` - PostgreSQL connection string
- `MINIO_ENDPOINT` - Internal MinIO endpoint for backend (e.g., minio:9000)
- `MINIO_EXTERNAL_ENDPOINT` - External MinIO endpoint for browser (e.g., localhost:9000)
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` - MinIO credentials
- `MINIO_SECURE` - Use HTTPS for MinIO ("true" or "false")

## Deployment Configurations

### Helm Values
Key configuration in helm/values.yaml:
- Backend/frontend image repositories and tags
- Service types (LoadBalancer, NodePort, ClusterIP)
- Resource limits for backend (CPU/memory for video processing)
- Storage class for persistent volumes
- PostgreSQL and MinIO sub-chart configurations
- Secrets for database and MinIO credentials

Production example: helm/values-production-example.yaml

### Storage Requirements
- PostgreSQL: ~10Gi for metadata
- MinIO: 50Gi+ depending on video volume (full game videos are large)
- Backend needs sufficient memory for ffmpeg processing (recommend 2Gi+)

## Testing Locally

1. Start services: `docker-compose up -d`
2. Wait for healthchecks to pass: `docker-compose ps`
3. Upload a game video at http://localhost:8080
4. Create clips with timestamps like "5:30" to "5:45"
5. Check processing: clips show pending → processing → completed status
6. Download or stream completed clips

Common issues:
- Video processing fails: check backend logs for ffmpeg errors
- MinIO access denied: verify MINIO_EXTERNAL_ENDPOINT matches your access method
- Clips stuck in processing: check backend container has enough memory

## Code Modification Guidelines

### Adding New API Endpoints
- Add route to backend/app.py
- Use asyncpg pool via `async with db_pool.acquire() as conn:`
- Use Pydantic models for request/response validation
- Convert UUIDs: `uuid.UUID(string_id)` when querying, `str(uuid_obj)` for JSON

### Frontend Changes
- Edit frontend/index.html directly
- Rebuild frontend container: `docker-compose up -d --build frontend`
- For Kubernetes: rebuild image and update deployment

### Database Schema Changes
- Modify CREATE TABLE statements in `lifespan()` function in backend/app.py
- For existing deployments, manually run ALTER statements in PostgreSQL
- No migration framework - handle schema evolution manually

### Video Processing Changes
- Modify `process_clip()` function in backend/app.py
- ffmpeg command at lines ~244-253
- Ensure temp file cleanup in /tmp directory
- Test with various video codecs and sizes

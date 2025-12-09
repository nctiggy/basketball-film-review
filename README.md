# Basketball Film Review 🏀

A comprehensive web application for basketball coaches to upload game videos, create annotated clips, and share them with players and parents. The platform provides role-based access with secure, isolated dashboards for each user type.

## Features

### For Coaches
- **Team Management**: Create teams, manage roster, invite players and parents
- **Game Video Upload**: Upload full game recordings with team color tracking
- **Clip Creation**: Extract clips using simple timestamps with automated processing
- **Rich Annotations**: Draw arrows, circles, and add text overlays on clips
- **Voice-Over Recording**: Add personal audio coaching to any clip
- **Player Assignments**: Assign clips to specific players with custom messages
- **Statistics Tracking**: Enter and track detailed player game statistics
- **Progress Monitoring**: See which players have viewed and acknowledged clips

### For Players
- **Personal Dashboard**: View only clips assigned specifically to you
- **Annotated Video**: Watch clips with coach's drawings and voice-over feedback
- **Statistics View**: Track your performance across games with detailed stats
- **Progress Tracking**: Mark clips as viewed and acknowledged
- **Mobile Responsive**: Access your content from any device

### For Parents
- **Child Monitoring**: View all content assigned to your children
- **Same Experience**: See exactly what your child sees (clips, stats, annotations)
- **Multiple Children**: Link to and switch between multiple children
- **Read-Only Access**: Stay informed without modifying any content

## Technical Features

- **Background Processing**: Clips processed asynchronously using ffmpeg and Kubernetes operators
- **Persistent Storage**: Videos stored safely in MinIO S3-compatible storage
- **Role-Based Security**: Strict access control ensures players only see their content
- **OAuth Integration**: Google OAuth for coach authentication
- **Easy Deployment**: Complete Kubernetes deployment with Helm and Flux CD
- **Automated CI/CD**: GitHub Actions pipeline with semantic versioning

## Architecture

- **Backend**: Python FastAPI with ffmpeg for video processing
- **Frontend**: HTML/CSS/JavaScript (vanilla, no framework dependencies)
- **Database**: PostgreSQL for metadata
- **Storage**: MinIO for video files
- **Deployment**: Kubernetes via Helm with all dependencies included

## Prerequisites

### For Local Development
- Docker and Docker Compose
- Python 3.11+ (optional, for local development)

### For Kubernetes Deployment
- Kubernetes cluster (1.24+)
- Helm 3.x
- kubectl configured to access your cluster
- Persistent Volume support (for PostgreSQL and MinIO)

## Documentation

Comprehensive documentation is available for all users:

### User Guides
- **[User Guide Overview](docs/user-guide/README.md)** - Getting started guide for all users
- **[Coach Guide](docs/user-guide/coach-guide.md)** - Complete guide for coaches covering team management, video upload, clip creation, annotations, assignments, and statistics
- **[Player Guide](docs/user-guide/player-guide.md)** - Guide for players to claim invites, view assigned clips, and track statistics
- **[Parent Guide](docs/user-guide/parent-guide.md)** - Guide for parents to link accounts and monitor their children's progress

### API Documentation
- **[API Overview](docs/api/README.md)** - API introduction, base URLs, and quick start
- **[Authentication](docs/api/authentication.md)** - Complete authentication guide (OAuth, JWT, registration)
- **[Endpoints Reference](docs/api/endpoints.md)** - Comprehensive reference for all API endpoints

### Developer Documentation
- **[Developer Guide](docs/developer/README.md)** - Local development setup, testing, and contributing guidelines

### Operations Documentation
- **[Operations Guide](docs/operations/README.md)** - Deployment, configuration, monitoring, and troubleshooting

## Quick Start - Local Development

### Using Docker Compose

1. Clone the repository:
```bash
git clone <your-repo-url>
cd basketball-film-review
```

2. Start all services:
```bash
docker-compose up -d
```

3. Access the application:
- **Web UI**: http://localhost:8080
- **API**: http://localhost:8000
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

4. Stop services:
```bash
docker-compose down
```

### Testing Locally

Once the application is running:

1. **Upload a game video**:
   - Go to http://localhost:8080
   - Fill in the game name and date
   - Select your video file
   - Click "Upload Game"

2. **Create clips**:
   - Select the game from the dropdown
   - Enter start time (e.g., "5:30") and end time (e.g., "5:45")
   - Add tags like "defense", "fast break", "player name"
   - Add optional notes
   - Click "Create Clip"

3. **View and download clips**:
   - Clips appear in the "Clips" section
   - Status will change from "pending" → "processing" → "completed"
   - Download completed clips

## Kubernetes Deployment

### Step 1: Build Docker Images

Build and push your Docker images to a registry your Kubernetes cluster can access:

```bash
# Set your registry (e.g., Docker Hub username, AWS ECR, etc.)
export IMAGE_REGISTRY="your-registry"
export IMAGE_TAG="v1.0.0"

# Build images
./build.sh
```

Or manually:

```bash
# Build backend
docker build -t your-registry/basketball-film-review-backend:v1.0.0 ./backend
docker push your-registry/basketball-film-review-backend:v1.0.0

# Build frontend
docker build -t your-registry/basketball-film-review-frontend:v1.0.0 ./frontend
docker push your-registry/basketball-film-review-frontend:v1.0.0
```

### Step 2: Prepare Helm Chart

1. Update dependencies:
```bash
cd helm
helm dependency update
```

This will download the PostgreSQL and MinIO Helm charts.

2. Create a custom `values-custom.yaml` file:
```yaml
# values-custom.yaml

backend:
  image:
    repository: your-registry/basketball-film-review-backend
    tag: v1.0.0

frontend:
  image:
    repository: your-registry/basketball-film-review-frontend
    tag: v1.0.0
  service:
    type: LoadBalancer  # or NodePort

# Storage class configuration (adjust for your cluster)
storageClass: ""  # Leave empty for default, or specify your storage class

# Update passwords for production
secrets:
  postgres:
    username: filmreview
    password: "CHANGE-THIS-PASSWORD"
    database: filmreview
  
  minio:
    rootUser: "admin"
    rootPassword: "CHANGE-THIS-PASSWORD"

postgresql:
  auth:
    username: filmreview
    password: "CHANGE-THIS-PASSWORD"
    database: filmreview
  primary:
    persistence:
      size: 10Gi
      storageClass: ""  # Your storage class

minio:
  rootUser: "admin"
  rootPassword: "CHANGE-THIS-PASSWORD"
  persistence:
    size: 50Gi
    storageClass: ""  # Your storage class
```

### Step 3: Deploy to Kubernetes

Install the application:

```bash
# Create namespace (optional)
kubectl create namespace film-review

# Install with Helm
helm install basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review
```

### Step 4: Access the Application

Wait for all pods to be ready:

```bash
kubectl get pods -n film-review -w
```

Get the frontend service URL:

```bash
# For LoadBalancer
kubectl get svc basketball-film-review-frontend -n film-review

# For NodePort
kubectl get svc basketball-film-review-frontend -n film-review -o jsonpath='{.spec.ports[0].nodePort}'
```

Access the application at the displayed IP/port.

### Step 5: (Optional) Configure Ingress

If you want to use an Ingress controller:

Update `values-custom.yaml`:

```yaml
ingress:
  enabled: true
  className: nginx  # or your ingress class
  hosts:
    - host: film-review.your-domain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: film-review-tls
      hosts:
        - film-review.your-domain.com
```

Then upgrade the deployment:

```bash
helm upgrade basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review
```

## Upgrading

To upgrade the application:

```bash
# Build new images with new tag
export IMAGE_TAG="v1.1.0"
./build.sh

# Update values-custom.yaml with new tag
# Then upgrade
helm upgrade basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review
```

## Uninstalling

```bash
helm uninstall basketball-film-review --namespace film-review

# Optional: Delete the namespace
kubectl delete namespace film-review
```

## Configuration Options

### Backend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.replicaCount` | Number of backend replicas | `1` |
| `backend.image.repository` | Backend image repository | `basketball-film-review-backend` |
| `backend.image.tag` | Backend image tag | `latest` |
| `backend.resources.limits.cpu` | CPU limit | `1000m` |
| `backend.resources.limits.memory` | Memory limit | `2Gi` |

### Frontend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `frontend.replicaCount` | Number of frontend replicas | `1` |
| `frontend.service.type` | Service type | `LoadBalancer` |
| `frontend.service.port` | Service port | `80` |

### PostgreSQL Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.auth.username` | Database username | `filmreview` |
| `postgresql.auth.password` | Database password | `filmreview` |
| `postgresql.primary.persistence.size` | Storage size | `10Gi` |

### MinIO Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.rootUser` | MinIO root user | `minioadmin` |
| `minio.rootPassword` | MinIO root password | `minioadmin` |
| `minio.persistence.size` | Storage size | `50Gi` |

## Usage Guide

### Creating Clips

1. **Upload Game Video**:
   - Enter a descriptive game name (e.g., "vs Warriors - Home Game")
   - Select the game date
   - Choose your video file (MP4, MOV, AVI supported)
   - Click upload (this may take a few minutes for large files)

2. **Create Clips**:
   - Select the game from the dropdown
   - Enter timestamps in `mm:ss` or `hh:mm:ss` format
     - Example: `5:30` to `5:45` for 30 seconds starting at 5:30
     - Example: `1:15:20` to `1:16:00` for 40 seconds
   - Add relevant tags:
     - Player names: "John Smith", "Jane Doe"
     - Play types: "fast break", "zone defense", "pick and roll"
     - Outcomes: "turnover", "made basket", "good defense"
   - Add notes for context
   - Click "Create Clip"

3. **Processing**:
   - Clips are processed in the background
   - Status updates automatically every 10 seconds
   - Processing time depends on clip length (usually < 30 seconds)

4. **Reviewing Clips**:
   - Filter clips by game or view all clips
   - Download individual clips for offline viewing
   - Share clips with players or assistants

### Tips for Organizing Film

- **Consistent Tags**: Use consistent tag names across clips
  - Use "defense" not "def" or "d"
  - Use "made basket" not "basket made" or "scored"

- **Multiple Tags**: Use multiple tags to categorize clips
  - Player name + play type + outcome
  - Example: "John Smith", "fast break", "made basket"

- **Descriptive Notes**: Add context that tags can't capture
  - "Great help defense rotation"
  - "Need to communicate on screens"

- **Organize by Game**: Keep game names consistent with dates
  - "2024-11-10 vs Warriors (Home)"
  - "2024-11-15 @ Lakers (Away)"

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n film-review

# Check pod logs
kubectl logs <pod-name> -n film-review

# Describe pod for events
kubectl describe pod <pod-name> -n film-review
```

### Storage Issues

If pods can't create PersistentVolumes:

1. Check if your cluster has a default storage class:
```bash
kubectl get storageclass
```

2. If not, create one or specify in `values-custom.yaml`:
```yaml
storageClass: "your-storage-class-name"
```

### Video Processing Fails

Check backend logs:
```bash
kubectl logs -n film-review -l component=backend -f
```

Common issues:
- Insufficient memory (increase backend resources)
- Corrupt video file (try re-uploading)
- Unsupported video codec (use common formats like H.264)

### Can't Access Frontend

Check service:
```bash
kubectl get svc basketball-film-review-frontend -n film-review
```

For LoadBalancer:
- Wait for EXTERNAL-IP to be assigned (may take a few minutes)
- Check cloud provider load balancer configuration

For NodePort:
- Access via any node IP and the assigned NodePort
- Ensure firewall allows traffic on that port

## API Documentation

The backend API is available at `/api`:

### Endpoints

- `GET /api/health` - Health check
- `GET /api/games` - List all games
- `POST /api/games` - Upload a new game (multipart/form-data)
- `GET /api/games/{id}` - Get specific game
- `GET /api/clips` - List all clips (supports ?game_id= and ?tag= filters)
- `POST /api/clips` - Create a new clip
- `GET /api/clips/{id}/download` - Download processed clip
- `DELETE /api/clips/{id}` - Delete a clip

See the FastAPI docs at `/docs` when running locally.

## Development

### Project Structure

```
basketball-film-review/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Backend container
├── frontend/
│   ├── index.html          # Web UI
│   ├── nginx.conf          # Nginx configuration
│   └── Dockerfile          # Frontend container
├── helm/
│   ├── Chart.yaml          # Helm chart definition
│   ├── values.yaml         # Default configuration
│   └── templates/          # Kubernetes manifests
│       ├── backend-deployment.yaml
│       ├── frontend-deployment.yaml
│       ├── secrets.yaml
│       └── ingress.yaml
├── docker-compose.yml      # Local development setup
├── build.sh                # Build script
└── README.md               # This file
```

### Contributing

1. Make changes to the code
2. Test locally with Docker Compose
3. Build new images
4. Test in Kubernetes
5. Submit pull request

## License

MIT License - feel free to use this for your team!

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review pod logs
3. Check Kubernetes events
4. Open an issue on GitHub

---

Made with ❤️ for youth basketball coaches

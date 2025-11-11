# Quick Start Guide

## Local Testing with Docker Compose

```bash
# Start everything
docker-compose up -d

# Access the app
open http://localhost:8080

# View logs
docker-compose logs -f

# Stop everything
docker-compose down
```

## Kubernetes Deployment

### 1. Build and Push Images

```bash
# Set your registry
export IMAGE_REGISTRY="your-dockerhub-username"
export IMAGE_TAG="v1.0.0"

# Build and push
./build.sh
```

### 2. Configure for Your Cluster

```bash
# Copy example values
cp helm/values-production-example.yaml helm/values-custom.yaml

# Edit the file and update:
# - Image registry/tags
# - Passwords
# - Storage classes
# - Service type (LoadBalancer/NodePort)
nano helm/values-custom.yaml
```

### 3. Deploy

```bash
# Interactive deployment
./deploy.sh

# Or manual deployment
cd helm
helm dependency update
cd ..

kubectl create namespace film-review

helm install basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review
```

### 4. Get Access URL

```bash
# For LoadBalancer
kubectl get svc basketball-film-review-frontend -n film-review

# For NodePort
kubectl get svc basketball-film-review-frontend -n film-review -o wide
```

## Using the Application

### Upload a Game

1. Go to the web UI
2. Fill in game details
3. Select video file
4. Click "Upload Game"

### Create Clips

1. Select the game
2. Enter timestamps (e.g., "5:30" to "5:45")
3. Add tags (player names, play types)
4. Add notes
5. Click "Create Clip"

### Download Clips

1. Wait for clip status to show "COMPLETED"
2. Click "Download Clip"
3. Share with players or use in film sessions

## Common Commands

```bash
# Check status
kubectl get pods -n film-review

# View backend logs
kubectl logs -n film-review -l component=backend -f

# View frontend logs
kubectl logs -n film-review -l component=frontend -f

# Port forward for local access
kubectl port-forward -n film-review svc/basketball-film-review-frontend 8080:80

# Upgrade deployment
helm upgrade basketball-film-review ./helm \
  -f ./helm/values-custom.yaml \
  --namespace film-review

# Uninstall
helm uninstall basketball-film-review -n film-review
```

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod <pod-name> -n film-review
kubectl logs <pod-name> -n film-review
```

### Storage issues
```bash
kubectl get pvc -n film-review
kubectl get storageclass
```

### Video processing fails
```bash
kubectl logs -n film-review -l component=backend -f
# Look for ffmpeg errors
```

## Tips

- Use consistent tag naming for easier searching
- Keep game names organized with dates
- Add descriptive notes to clips
- Regular backups of PostgreSQL database recommended
- Monitor MinIO storage usage

## Need Help?

Check the full README.md for detailed documentation.

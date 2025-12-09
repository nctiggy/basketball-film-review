# Operations Guide

This guide covers deployment, configuration, monitoring, and troubleshooting for the Basketball Film Review application.

## Table of Contents

- [Deployment](#deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Backup and Recovery](#backup-and-recovery)
- [Security](#security)

## Deployment

### Kubernetes Deployment with Helm

See [Deployment Guide](deployment.md) for complete instructions.

**Quick Deploy:**

```bash
# Set your registry
export IMAGE_REGISTRY="nctiggy"
export IMAGE_TAG="1.10.0"

# Build and push images (if needed)
./build.sh

# Deploy to Kubernetes
export KUBECONFIG=admin.app-eng.kubeconfig
helm upgrade --install basketball-film-review ./helm \
  --namespace film-review \
  --create-namespace
```

### CI/CD Pipeline

The application uses GitHub Actions for CI/CD:

1. **Push to main** → Triggers build
2. **GitHub Actions** → Builds images, updates tags, commits to Git
3. **Flux CD** → Deploys to Kubernetes automatically

See `.github/workflows/build-and-push.yml` for pipeline details.

## Configuration

### Environment Variables

**Backend (`backend/app.py`):**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `MINIO_ENDPOINT` | Internal MinIO endpoint | `minio:9000` | Yes |
| `MINIO_EXTERNAL_ENDPOINT` | External MinIO endpoint | `localhost:9000` | Yes |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` | Yes |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` | Yes |
| `MINIO_SECURE` | Use HTTPS for MinIO | `false` | No |
| `JWT_SECRET` | JWT signing secret | - | Yes |
| `JWT_EXPIRATION_HOURS` | Access token expiration | `24` | No |
| `REFRESH_TOKEN_DAYS` | Refresh token expiration | `7` | No |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | - | Yes (coaches) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | - | Yes (coaches) |

### Helm Values

See `helm/values.yaml` for all configuration options.

**Key configurations:**

```yaml
# Image configuration
backend:
  image:
    repository: nctiggy/basketball-film-review-backend
    tag: "1.10.0"
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi

# Service type
frontend:
  service:
    type: LoadBalancer  # or NodePort for local

# Secrets
secrets:
  postgres:
    password: "change-in-production"
  minio:
    rootPassword: "change-in-production"
  jwt:
    secret: "change-in-production"
  google:
    clientId: "your-client-id"
    clientSecret: "your-client-secret"
```

## Monitoring

### Health Checks

**API Health:**
```bash
curl http://your-domain/health
# Response: {"status": "healthy"}
```

**Kubernetes Probes:**

All pods have liveness and readiness probes configured:

```bash
kubectl get pods -n film-review
kubectl describe pod <pod-name> -n film-review
```

### Logs

**View application logs:**
```bash
# Backend logs
kubectl logs -n film-review -l component=backend -f

# Frontend logs
kubectl logs -n film-review -l component=frontend -f

# All logs
kubectl logs -n film-review --all-containers -f
```

**Common log patterns:**
- `"Created ClipJob for clip"` - Clip processing started
- `"Google authentication failed"` - OAuth issues
- `"Rate limit exceeded"` - User hitting rate limits
- `"Error creating AnalysisJob"` - AI analysis failures

### Metrics

Monitor these key metrics:

**Resource Usage:**
```bash
kubectl top pods -n film-review
kubectl top nodes
```

**Storage:**
```bash
# Check PVC usage
kubectl get pvc -n film-review

# Check disk space on MinIO
kubectl exec -n film-review deployment/minio -- df -h
```

### Flux CD Monitoring

```bash
export KUBECONFIG=admin.app-eng.kubeconfig

# Check Flux status
flux get all -A

# Check HelmRelease
flux get helmrelease -n film-review

# Check image automation
flux get image repository -A
flux get image policy -A

# View Flux logs
kubectl logs -n flux-system deployment/helm-controller -f
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n film-review

# View pod events
kubectl describe pod <pod-name> -n film-review

# Check logs
kubectl logs <pod-name> -n film-review --previous
```

**Common issues:**
- **ImagePullBackOff**: Image not found or credentials invalid
- **CrashLoopBackOff**: Application failing to start (check logs)
- **Pending**: Insufficient resources or PVC not bound

### Database Issues

**Connection failures:**
```bash
# Check PostgreSQL pod
kubectl get pods -n film-review | grep postgres

# Check PostgreSQL logs
kubectl logs -n film-review -l app.kubernetes.io/name=postgresql -f

# Test connection from backend
kubectl exec -n film-review deployment/basketball-film-review-backend -- \
  python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))"
```

**Database migrations:**
```bash
# Connect to database
kubectl exec -it -n film-review <postgres-pod> -- psql -U filmreview -d filmreview

# List tables
\dt

# Check table schema
\d users
```

### MinIO Issues

**Connection problems:**
```bash
# Check MinIO pod
kubectl get pods -n film-review | grep minio

# Test MinIO connectivity
kubectl exec -n film-review deployment/basketball-film-review-backend -- \
  python -c "from minio import Minio; m = Minio('minio:9000', 'minioadmin', 'minioadmin', secure=False); print(m.bucket_exists('basketball-clips'))"
```

**Storage full:**
```bash
# Check MinIO storage usage
kubectl exec -n film-review deployment/minio -- df -h

# If full, expand PVC or clean up old files
```

### Video Processing Failures

**Clip stuck in processing:**
```bash
# Check ClipJob status
kubectl get clipjobs -n film-review

# View ClipJob details
kubectl describe clipjob clip-<clip-id> -n film-review

# Check operator logs
kubectl logs -n film-review -l app=clip-operator -f
```

**ffmpeg errors:**
```bash
# Check backend logs for ffmpeg output
kubectl logs -n film-review -l component=backend | grep ffmpeg
```

### Authentication Issues

**Google OAuth not working:**
```bash
# Verify Google OAuth credentials
kubectl get secret basketball-film-review-secrets -n film-review -o yaml

# Check backend logs for OAuth errors
kubectl logs -n film-review -l component=backend | grep "Google authentication"
```

**JWT token errors:**
```bash
# Verify JWT secret is set
kubectl get secret basketball-film-review-secrets -n film-review -o jsonpath='{.data.jwt-secret}' | base64 -d

# Check for expired tokens in logs
kubectl logs -n film-review -l component=backend | grep "Token has expired"
```

### Performance Issues

**Slow API responses:**
```bash
# Check pod resources
kubectl top pods -n film-review

# Increase backend resources if needed
kubectl edit deployment basketball-film-review-backend -n film-review
# Update resources.limits.cpu and resources.limits.memory
```

**Database slow queries:**
```bash
# Connect to PostgreSQL
kubectl exec -it -n film-review <postgres-pod> -- psql -U filmreview -d filmreview

# Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
```

## Backup and Recovery

### Database Backup

**Manual backup:**
```bash
# Export database
kubectl exec -n film-review <postgres-pod> -- \
  pg_dump -U filmreview filmreview | gzip > backup-$(date +%Y%m%d).sql.gz
```

**Restore database:**
```bash
# Import database
gunzip -c backup-20240120.sql.gz | \
  kubectl exec -i -n film-review <postgres-pod> -- \
  psql -U filmreview -d filmreview
```

### MinIO Backup

**Backup video files:**
```bash
# Use MinIO client to mirror bucket
kubectl port-forward -n film-review svc/minio 9000:9000
mc mirror local/basketball-clips ./minio-backup/
```

**Restore files:**
```bash
mc mirror ./minio-backup/ local/basketball-clips
```

### Automated Backups

Consider implementing:
- **Velero** for Kubernetes backup
- **PostgreSQL automated backups** (daily dumps to S3)
- **MinIO replication** to another storage backend

## Security

### Secrets Management

**Rotate secrets:**
```bash
# Generate new JWT secret
NEW_JWT_SECRET=$(openssl rand -base64 32)

# Update secret
kubectl create secret generic basketball-film-review-secrets \
  --from-literal=jwt-secret=$NEW_JWT_SECRET \
  --namespace film-review \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart backend to use new secret
kubectl rollout restart deployment/basketball-film-review-backend -n film-review
```

### Access Control

**RBAC:**
- Ensure proper Kubernetes RBAC roles
- Limit service account permissions
- Use network policies to restrict pod communication

**Application:**
- All endpoints require authentication (except public invite preview)
- Role-based access control enforced
- Rate limiting prevents abuse

### Security Updates

**Update dependencies:**
```bash
# Backend
cd backend
pip list --outdated
pip install --upgrade <package>

# Rebuild and deploy
./build.sh
helm upgrade basketball-film-review ./helm -n film-review
```

**Monitor CVEs:**
- Use `safety check` for Python dependencies
- Scan container images with `trivy`
- Enable Dependabot for GitHub repositories

## Scaling

### Horizontal Scaling

**Scale backend:**
```bash
kubectl scale deployment basketball-film-review-backend \
  --replicas=3 -n film-review
```

Or update `helm/values.yaml`:
```yaml
backend:
  replicaCount: 3
```

### Vertical Scaling

**Increase resources:**
```yaml
backend:
  resources:
    limits:
      cpu: 2000m      # Increase CPU
      memory: 4Gi     # Increase memory
```

### Storage Scaling

**Expand PVC:**
```bash
kubectl edit pvc <pvc-name> -n film-review
# Update spec.resources.requests.storage to larger size
```

Note: Storage class must support volume expansion.

## Disaster Recovery

### Recovery Plan

1. **Restore database** from latest backup
2. **Restore MinIO files** from backup
3. **Redeploy application** using Helm
4. **Verify functionality** with health checks
5. **Notify users** of recovery completion

### Testing Recovery

Regularly test disaster recovery:
```bash
# 1. Create backup
# 2. Delete namespace
kubectl delete namespace film-review
# 3. Recreate from backup
# 4. Verify all data restored
```

## Maintenance

### Regular Maintenance Tasks

**Weekly:**
- Review logs for errors
- Check disk usage
- Monitor performance metrics

**Monthly:**
- Review and rotate logs
- Update dependencies
- Review access logs
- Clean up old data (if needed)

**Quarterly:**
- Test backup and recovery
- Security audit
- Performance tuning
- Review and update documentation

### Upgrading

**Application upgrade:**
```bash
# Update image tags in values.yaml
# Then upgrade
helm upgrade basketball-film-review ./helm -n film-review
```

**Rolling back:**
```bash
helm rollout undo basketball-film-review -n film-review
```

## Support

For issues:
1. Check logs first
2. Review this troubleshooting guide
3. Check GitHub issues
4. Contact development team

**Include in support requests:**
- Pod logs
- `kubectl describe` output
- Steps to reproduce
- Expected vs actual behavior

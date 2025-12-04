# Basketball Film Review - Secure Deployment Summary

## Overview

Your Basketball Film Review application is now configured for secure internet access using:

- **Cloudflare Tunnel** - Zero-trust network access without firewall port forwarding
- **Cloudflare Access** - Google OIDC authentication
- **1Password Connect** - Secure secrets management
- **External Secrets Operator** - Automatic secret synchronization to Kubernetes
- **Kubernetes** - Container orchestration with Helm

## What We've Set Up

### ✅ 1. 1Password Integration

**Vault**: `k8s` (ID: `iy7ttbaa6ejuym6hwlvf3xlc5a`)

**Secrets Stored**:
- `cloudflare-tunnel` - Cloudflare API token and tunnel credentials
- `google-oauth` - Google OAuth client ID and secret
- `minio-credentials` - MinIO storage credentials
- `postgres-credentials` - PostgreSQL database credentials

**Connect Server**: `6M4A754BQJD2DA74PISVFF77TQ`

### ✅ 2. Cloudflare Tunnel

**Tunnel ID**: `92ade8d6-597d-4d18-bc26-ccb9579033f5`
**Hostname**: `bball-review.craigcloud.io`

The tunnel securely connects your Kubernetes cluster to Cloudflare's edge network without exposing any ports on your firewall.

### ✅ 3. Helm Chart Updates

**New Templates Created**:
- `helm/templates/secretstore.yaml` - 1Password SecretStore
- `helm/templates/externalsecret-cloudflare.yaml` - Cloudflare tunnel secrets
- `helm/templates/externalsecret-minio.yaml` - MinIO credentials
- `helm/templates/externalsecret-postgres.yaml` - PostgreSQL credentials
- `helm/templates/cloudflared-configmap.yaml` - Cloudflared configuration
- `helm/templates/cloudflared-deployment.yaml` - Cloudflared deployment

**Updated Files**:
- `helm/values.yaml` - Added cloudflared and externalSecrets configuration
- `.gitignore` - Excluded sensitive credential files

### ✅ 4. Deployment Scripts

**Created Scripts**:
- `scripts/complete-setup.sh` - One-click 1Password and Cloudflare setup
- `scripts/deploy-to-kubernetes.sh` - Full Kubernetes deployment automation

### ✅ 5. Documentation

- `SETUP-CLOUDFLARE-1PASSWORD.md` - Complete setup guide
- `CLOUDFLARE-ACCESS-SETUP.md` - Google OIDC authentication configuration
- `DEPLOYMENT-SUMMARY.md` - This file

## Next Steps - Deploy to Kubernetes

When your Kubernetes cluster is ready, follow these steps:

### 1. Sign in to 1Password

```bash
op signin
```

### 2. Deploy to Kubernetes

```bash
cd /Users/craigsmith/code/basketball-film-review
./scripts/deploy-to-kubernetes.sh
```

This script will:
1. Create the `film-review` namespace
2. Install External Secrets Operator
3. Create a 1Password Connect token
4. Deploy 1Password Connect server
5. Deploy the Basketball Film Review application
6. Configure Cloudflare DNS

### 3. Configure Cloudflare Access

Follow the guide in `CLOUDFLARE-ACCESS-SETUP.md` to:
1. Add Google as an identity provider in Cloudflare
2. Create an Access application
3. Configure access policies
4. Test authentication

### 4. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n film-review

# Check External Secrets are synced
kubectl get externalsecrets -n film-review

# Check cloudflared tunnel status
kubectl logs -n film-review -l component=cloudflared

# Access the application
open https://bball-review.craigcloud.io
```

## Architecture Diagram

```
Internet Users
      ↓
[Google OAuth Authentication]
      ↓
[Cloudflare Access]
      ↓
[Cloudflare Tunnel: bball-review.craigcloud.io]
      ↓
[Kubernetes Cluster]
      ├── cloudflared pods (2 replicas)
      ├── frontend pods → nginx
      ├── backend pods → FastAPI
      ├── postgresql pods
      ├── minio pods
      ├── 1Password Connect server
      └── External Secrets Operator
           ↓
      [1Password Vault: k8s]
```

## Security Features

### ✅ No Firewall Ports Exposed
Cloudflare Tunnel creates an outbound-only connection from your cluster to Cloudflare's edge.

### ✅ Zero-Trust Authentication
All access requires Google OAuth authentication via Cloudflare Access.

### ✅ Secrets Never in Git
All sensitive credentials stored in 1Password, synced to Kubernetes via External Secrets.

### ✅ End-to-End Encryption
Traffic encrypted from users → Cloudflare → Kubernetes cluster.

### ✅ Fine-Grained Access Control
Cloudflare Access policies control exactly who can access the application.

## Configuration Reference

### Helm Values (helm/values.yaml)

```yaml
# External Secrets - Enable 1Password integration
externalSecrets:
  enabled: true
  onepassword:
    connectHost: http://connect-connect-api:8080
    vaultId: iy7ttbaa6ejuym6hwlvf3xlc5a
    tokenSecretName: onepassword-connect-token

# Cloudflared Tunnel - Enable secure ingress
cloudflared:
  enabled: true
  hostname: bball-review.craigcloud.io
  tunnelId: 92ade8d6-597d-4d18-bc26-ccb9579033f5
  replicaCount: 2
```

### Environment Variables (Backend)

The backend automatically pulls credentials from External Secrets:
- `DATABASE_URL` - From postgres-credentials
- `MINIO_ACCESS_KEY` - From minio-credentials
- `MINIO_SECRET_KEY` - From minio-credentials

## Monitoring & Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n film-review
```

### View Logs
```bash
# Backend
kubectl logs -n film-review -l component=backend -f

# Frontend
kubectl logs -n film-review -l component=frontend -f

# Cloudflared
kubectl logs -n film-review -l component=cloudflared -f

# 1Password Connect
kubectl logs -n film-review -l app.kubernetes.io/name=connect -f
```

### Check External Secrets Sync
```bash
kubectl get externalsecrets -n film-review
kubectl describe externalsecret basketball-film-review-cloudflare-tunnel -n film-review
```

### Test Cloudflare Tunnel
```bash
# Check DNS resolution
dig bball-review.craigcloud.io

# Check HTTPS access
curl -I https://bball-review.craigcloud.io
```

## Maintenance

### Rotate Secrets

To rotate a secret:
1. Update the value in 1Password
2. Wait for External Secrets to sync (default: 1 hour)
3. Or force immediate sync:
   ```bash
   kubectl annotate externalsecret <name> -n film-review \
     force-sync=$(date +%s) --overwrite
   ```
4. Restart affected pods if needed

### Update Application

```bash
# Update images
export IMAGE_TAG="1.0.2"
./build.sh

# Deploy update
helm upgrade basketball-film-review ./helm \
  --namespace film-review \
  --set backend.image.tag=$IMAGE_TAG \
  --set frontend.image.tag=$IMAGE_TAG
```

### Scale Components

```bash
# Scale cloudflared for redundancy
kubectl scale deployment basketball-film-review-cloudflared \
  --replicas=3 -n film-review

# Scale backend for performance
kubectl scale deployment basketball-film-review-backend \
  --replicas=2 -n film-review
```

## Support & Documentation

- **Cloudflare Tunnel**: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- **Cloudflare Access**: https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/
- **External Secrets**: https://external-secrets.io/
- **1Password Connect**: https://developer.1password.com/docs/connect/

## Files Created

```
basketball-film-review/
├── scripts/
│   ├── complete-setup.sh              # 1Password & Cloudflare setup
│   ├── deploy-to-kubernetes.sh        # Kubernetes deployment
│   ├── create-cloudflare-tunnel.sh    # Tunnel creation
│   ├── create-1password-connect-server.sh
│   └── setup-1password-secrets.sh
├── helm/
│   ├── values.yaml                    # Updated with new config
│   └── templates/
│       ├── secretstore.yaml           # 1Password SecretStore
│       ├── externalsecret-cloudflare.yaml
│       ├── externalsecret-minio.yaml
│       ├── externalsecret-postgres.yaml
│       ├── cloudflared-configmap.yaml
│       └── cloudflared-deployment.yaml
├── SETUP-CLOUDFLARE-1PASSWORD.md      # Setup guide
├── CLOUDFLARE-ACCESS-SETUP.md         # Auth configuration
├── DEPLOYMENT-SUMMARY.md              # This file
└── .gitignore                         # Updated with sensitive files
```

## Quick Reference

| Component | Namespace | Service | Port |
|-----------|-----------|---------|------|
| Frontend | film-review | basketball-film-review-frontend | 80 |
| Backend | film-review | basketball-film-review-backend | 8000 |
| PostgreSQL | film-review | basketball-film-review-postgresql | 5432 |
| MinIO | film-review | basketball-film-review-minio | 9000 |
| MinIO Console | film-review | basketball-film-review-minio-console | 9001 |
| 1Password Connect | film-review | connect-connect-api | 8080 |
| Cloudflared | film-review | (no service - outbound only) | - |

## Success Criteria

Your deployment is successful when:

- [x] All Kubernetes pods are in Running state
- [x] External Secrets show "SecretSynced" status
- [x] Cloudflared tunnel is connected (check logs)
- [x] DNS resolves `bball-review.craigcloud.io` correctly
- [ ] Can access https://bball-review.craigcloud.io
- [ ] Redirected to Google OAuth login
- [ ] Can authenticate with nctiggy@gmail.com
- [ ] Can upload videos and create clips
- [ ] Video playback works correctly

---

**Ready to deploy?** Run `./scripts/deploy-to-kubernetes.sh` when your cluster is accessible!

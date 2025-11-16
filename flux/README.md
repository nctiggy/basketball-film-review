# Flux GitOps Setup

This directory contains Flux CD configurations for automatic deployment of the Basketball Film Review application.

## Architecture

```
GitHub Actions (CI)          Flux CD (CD)
─────────────────────        ────────────────
1. Code push to main    →
2. Build Docker images
3. Push to Docker Hub   →    4. Flux detects new images
4. Update helm/values.yaml → 5. Flux updates HelmRelease
                             6. Application deployed
```

## Components

### GitRepository (`gitrepository.yaml`)
- Watches the `main` branch of this repository
- Polls every 1 minute for changes
- Only syncs `/helm` and `/flux` directories

### HelmRelease (`helmrelease.yaml`)
- Manages the Helm deployment in the `film-review` namespace
- Auto-upgrades when Helm values change
- Retries failed installations/upgrades 3 times

### Image Automation
- **ImageRepository**: Scans Docker Hub for new images
- **ImagePolicy**: Determines which image versions to use (semver >=1.0.0)
- **ImageUpdateAutomation**: Automatically updates `helm/values.yaml` when new images are pushed

## Setup Instructions

### 1. Install Flux (Already Done)
```bash
flux install --components-extra=image-reflector-controller,image-automation-controller
```

### 2. Create GitHub Personal Access Token
For Flux to push image tag updates back to GitHub:

1. Go to https://github.com/settings/tokens/new
2. Create a token with these scopes:
   - `repo` (all)
3. Save the token securely

### 3. Create Flux Secret for Git Push
```bash
export KUBECONFIG=admin.app-eng.kubeconfig
export GITHUB_TOKEN=<your-github-pat>

kubectl create secret generic flux-system \
  --namespace=flux-system \
  --from-literal=username=git \
  --from-literal=password=${GITHUB_TOKEN}
```

### 4. Update ImageUpdateAutomation to use secret
The `image-update.yaml` needs to reference this secret for authentication.

### 5. Configure GitHub Secrets for Actions
In your GitHub repository settings, add these secrets:
- `DOCKER_USERNAME`: Your Docker Hub username (nctiggy)
- `DOCKER_PASSWORD`: Your Docker Hub password or access token

## How It Works

### Automatic Deployment Flow

1. **Developer pushes code** to `main` branch
2. **GitHub Actions** triggers:
   - Detects changes (backend or frontend)
   - Bumps semantic version based on commit messages
   - Builds AMD64 Docker images
   - Pushes images to Docker Hub with version tag
   - Updates `helm/values.yaml` with new version
   - Commits and pushes changes back to GitHub
3. **Flux watches** the Git repository and Docker Hub:
   - Detects updated `helm/values.yaml`
   - Deploys new Helm release to cluster
4. **Application updates** automatically

### Semantic Versioning

Commit message prefixes control version bumps:
- `feat:` or `feature:` → Minor version bump (1.0.0 → 1.1.0)
- `fix:` or `bugfix:` → Patch version bump (1.0.0 → 1.0.1)
- `BREAKING CHANGE:` or `feat!:` → Major version bump (1.0.0 → 2.0.0)
- Anything else → Patch version bump

### Monitoring

Check Flux status:
```bash
export KUBECONFIG=admin.app-eng.kubeconfig

# Overall status
flux get all -A

# HelmRelease status
flux get helmrelease -n film-review

# Image automation status
flux get image repository -A
flux get image policy -A
flux get image update -A

# Logs
kubectl logs -n flux-system deployment/image-reflector-controller -f
kubectl logs -n flux-system deployment/image-automation-controller -f
kubectl logs -n flux-system deployment/helm-controller -f
```

## Future: Multi-Environment Support

To add staging/dev environments later:

1. Create environment-specific overlays:
   ```
   flux/
   ├── base/              # Shared configs
   ├── environments/
   │   ├── dev/          # Dev-specific values
   │   ├── staging/      # Staging-specific values
   │   └── production/   # Production-specific values
   ```

2. Create separate HelmReleases per environment
3. Use Kustomize or Helm value overrides for environment-specific configs
4. Add GitHub Actions environments with approval workflows

## Disabling Flux (Temporary)

If you need to deploy manually:
```bash
# Suspend Flux automation
flux suspend helmrelease basketball-film-review -n film-review
flux suspend image update basketball-film-review

# Deploy manually with Helm
helm upgrade basketball-film-review ./helm -n film-review

# Resume Flux
flux resume helmrelease basketball-film-review -n film-review
flux resume image update basketball-film-review
```

## Troubleshooting

### HelmRelease stuck or failing
```bash
# Check status
flux get helmrelease basketball-film-review -n film-review

# View events
kubectl describe helmrelease basketball-film-review -n film-review

# Force reconciliation
flux reconcile helmrelease basketball-film-review -n film-review --with-source
```

### Image automation not updating
```bash
# Check image repositories are scanning
flux get image repository -A

# Check image policies are resolving
flux get image policy -A

# Manually trigger update
flux reconcile image update basketball-film-review --with-source
```

### Git push failing
- Verify GitHub token has correct permissions
- Check the `flux-system` secret exists in `flux-system` namespace
- Ensure token hasn't expired

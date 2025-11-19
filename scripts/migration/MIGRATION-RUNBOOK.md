# PostgreSQL & MinIO Migration Runbook

## Overview
Migrate PostgreSQL and MinIO from Helm sub-charts to standalone deployments.

**Current State:**
- PostgreSQL: 7.7 MB database (sub-chart)
- MinIO: 1.7 GB in basketball-clips bucket (sub-chart)

**Target State:**
- Standalone PostgreSQL release named `postgresql`
- Standalone MinIO release named `minio`
- Both in `film-review` namespace

## Pre-Migration Checklist

- [ ] PV reclaim policies set to Retain (verified)
- [ ] Backup scripts tested
- [ ] Flux suspended to prevent conflicts
- [ ] Application scaled down during migration

---

## Step 1: Suspend Flux

Prevent Flux from interfering during migration:

```bash
export KUBECONFIG=/Users/craigsmith/code/basketball-film-review/admin.app-eng.kubeconfig
flux suspend helmrelease basketball-film-review -n film-review
```

## Step 2: Deploy Standalone PostgreSQL

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install postgresql bitnami/postgresql \
  -n film-review \
  -f scripts/migration/postgresql-values.yaml
```

Wait for pod to be ready:
```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -n film-review --timeout=120s
```

## Step 3: Migrate PostgreSQL Data

Create backup from old instance:
```bash
kubectl exec -n film-review basketball-film-review-postgresql-0 -- \
  pg_dump -U filmreview -d filmreview -Fc > /tmp/filmreview_backup.dump
```

Copy to new instance:
```bash
kubectl cp /tmp/filmreview_backup.dump film-review/postgresql-0:/tmp/filmreview_backup.dump
```

Restore to new instance:
```bash
kubectl exec -n film-review postgresql-0 -- \
  pg_restore -U filmreview -d filmreview -c /tmp/filmreview_backup.dump
```

Verify data:
```bash
kubectl exec -n film-review postgresql-0 -- \
  psql -U filmreview -d filmreview -c "SELECT COUNT(*) FROM games; SELECT COUNT(*) FROM videos; SELECT COUNT(*) FROM clips;"
```

## Step 4: Deploy Standalone MinIO

```bash
helm repo add minio https://charts.min.io/
helm repo update

helm install minio minio/minio \
  -n film-review \
  -f scripts/migration/minio-values.yaml
```

Wait for pod to be ready:
```bash
kubectl wait --for=condition=ready pod -l app=minio -n film-review --timeout=120s
```

## Step 5: Migrate MinIO Data

Port-forward both MinIO instances:
```bash
# Terminal 1: Old MinIO
kubectl port-forward -n film-review svc/basketball-film-review-minio 9000:9000

# Terminal 2: New MinIO
kubectl port-forward -n film-review svc/minio 9001:9000
```

Install mc client (if not installed):
```bash
brew install minio/stable/mc
```

Configure mc aliases:
```bash
mc alias set old-minio http://localhost:9000 minioadmin minioadmin
mc alias set new-minio http://localhost:9001 minioadmin minioadmin
```

Mirror data:
```bash
mc mirror --preserve old-minio/basketball-clips new-minio/basketball-clips
```

Verify:
```bash
mc ls new-minio/basketball-clips --recursive --summarize
```

## Step 6: Update Application Configuration

Update helm/values.yaml backend env vars:

```yaml
backend:
  env:
    - name: DATABASE_URL
      value: "postgresql://filmreview:filmreview@postgresql:5432/filmreview"
    - name: MINIO_ENDPOINT
      value: "minio:9000"
    - name: MINIO_ACCESS_KEY
      value: "minioadmin"
    - name: MINIO_SECRET_KEY
      value: "minioadmin"
    - name: MINIO_SECURE
      value: "false"

# Disable sub-charts
postgresql:
  enabled: false

minio:
  enabled: false
```

Deploy updated chart:
```bash
helm upgrade basketball-film-review ./helm -n film-review
```

## Step 7: Verify Migration

Check backend can connect:
```bash
kubectl logs -n film-review -l component=backend --tail=50
```

Test application:
- Visit the frontend
- Verify games/videos/clips load
- Try playing a clip

## Step 8: Resume Flux

```bash
flux resume helmrelease basketball-film-review -n film-review
```

## Step 9: Cleanup (After Verification)

**WARNING: Only after confirming everything works!**

The old sub-chart resources will be removed when helm chart is upgraded with disabled sub-charts.

Old PVCs can be manually deleted if no longer needed:
```bash
# DANGER: Only after full verification
kubectl delete pvc data-basketball-film-review-postgresql-0 -n film-review
kubectl delete pvc basketball-film-review-minio -n film-review
```

---

## Rollback Plan

If migration fails:

1. Re-enable sub-charts in values.yaml
2. Restore original backend env vars
3. Deploy: `helm upgrade basketball-film-review ./helm -n film-review`
4. Delete standalone deployments:
   ```bash
   helm uninstall postgresql -n film-review
   helm uninstall minio -n film-review
   ```
5. Resume Flux

PV data is preserved due to Retain policy.

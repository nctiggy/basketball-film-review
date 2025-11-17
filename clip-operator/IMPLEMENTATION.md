# Clip Operator Implementation Guide

## What We've Built So Far

### 1. CRD Definition (`manifests/clipjob-crd.yaml`) ✅
- Defines ClipJob custom resource
- Includes spec for clip parameters
- Status tracking for job lifecycle

### 2. Operator (`src/operator.py`) ✅
- Kopf-based Python operator
- Creates Kubernetes Jobs when ClipJob is created
- Updates ClipJob status based on Job completion
- Automatic cleanup via TTL

### 3. Worker (`worker/process_clip.py`) ✅
- Downloads video from MinIO
- Uses ffmpeg with GPU acceleration (h264_nvenc)
- Uploads finished clip
- Updates database status

## Files Still Needed

### 4. Worker Dockerfile

Create `worker/Dockerfile`:
```dockerfile
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Install Python and ffmpeg with NVIDIA support
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY process_clip.py .

CMD ["python3", "process_clip.py"]
```

Create `worker/requirements.txt`:
```
minio==7.2.0
asyncpg==0.29.0
```

### 5. Operator Dockerfile

Create `src/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY operator.py .

CMD ["kopf", "run", "--standalone", "operator.py"]
```

Create `src/requirements.txt`:
```
kopf==1.37.2
kubernetes==28.1.0
```

### 6. Operator Deployment

Create `manifests/operator-deployment.yaml`:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: clip-operator
  namespace: film-review
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: clip-operator
rules:
  - apiGroups: ["filmreview.io"]
    resources: ["clipjobs", "clipjobs/status"]
    verbs: ["get", "list", "watch", "patch"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: [""]
    resources: ["events"]
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: clip-operator
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: clip-operator
subjects:
  - kind: ServiceAccount
    name: clip-operator
    namespace: film-review
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clip-operator
  namespace: film-review
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clip-operator
  template:
    metadata:
      labels:
        app: clip-operator
    spec:
      serviceAccountName: clip-operator
      containers:
        - name: operator
          image: nctiggy/clip-operator:latest
          imagePullPolicy: Always
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "200m"
```

### 7. Backend Changes

In `backend/app.py`, replace the `create_clip()` endpoint processing:

```python
from kubernetes import client, config

# Load k8s config (in-cluster)
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

@app.post("/clips", response_model=Clip)
async def create_clip(request: CreateClipRequest):
    """Create a new clip - now creates a ClipJob instead of processing directly"""
    clip_id = str(uuid.uuid4())

    # Insert clip record with pending status
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clips (id, game_id, video_id, start_time, end_time, tags, players, notes, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            """,
            uuid.UUID(clip_id),
            uuid.UUID(request.game_id),
            uuid.UUID(request.video_id),
            request.start_time,
            request.end_time,
            request.tags,
            request.players or [],
            request.notes
        )

        # Get video path
        video_row = await conn.fetchrow(
            "SELECT game_id, filename FROM videos WHERE id = $1",
            uuid.UUID(request.video_id)
        )

    # Build paths
    video_path = f"games/{video_row['game_id']}/{request.video_id}_{video_row['filename']}"
    clip_path = f"clips/{clip_id}.mp4"

    # Create ClipJob custom resource
    clipjob = {
        "apiVersion": "filmreview.io/v1alpha1",
        "kind": "ClipJob",
        "metadata": {
            "name": f"clip-{clip_id[:8]}",
            "namespace": "film-review",
        },
        "spec": {
            "clipId": clip_id,
            "gameId": request.game_id,
            "videoId": request.video_id,
            "startTime": request.start_time,
            "endTime": request.end_time,
            "videoPath": video_path,
            "clipPath": clip_path,
        }
    }

    # Create the ClipJob
    api = client.CustomObjectsApi()
    try:
        api.create_namespaced_custom_object(
            group="filmreview.io",
            version="v1alpha1",
            namespace="film-review",
            plural="clipjobs",
            body=clipjob
        )
    except Exception as e:
        logger.error(f"Failed to create ClipJob: {e}")
        # Update clip status to failed
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clips SET status = 'failed' WHERE id = $1",
                uuid.UUID(clip_id)
            )
        raise HTTPException(status_code=500, detail=f"Failed to create clip job: {e}")

    return {
        "id": clip_id,
        "game_id": request.game_id,
        "video_id": request.video_id,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "tags": request.tags,
        "players": request.players or [],
        "notes": request.notes,
        "clip_path": None,
        "status": "pending",
        "created_at": datetime.now()
    }
```

## Build and Deploy Steps

### 1. Build Worker Image
```bash
cd clip-operator/worker
docker buildx build --platform linux/amd64 -t nctiggy/clip-processor:latest --push .
```

### 2. Build Operator Image
```bash
cd ../src
docker buildx build --platform linux/amd64 -t nctiggy/clip-operator:latest --push .
```

### 3. Deploy CRD
```bash
kubectl apply -f clip-operator/manifests/clipjob-crd.yaml
```

### 4. Deploy Operator
```bash
kubectl apply -f clip-operator/manifests/operator-deployment.yaml
```

### 5. Update Backend
- Add kubernetes library to backend requirements
- Update create_clip endpoint
- Rebuild and deploy backend

## Testing

```bash
# Create a test ClipJob
kubectl apply -f - <<EOF
apiVersion: filmreview.io/v1alpha1
kind: ClipJob
metadata:
  name: test-clip
  namespace: film-review
spec:
  clipId: "test-123"
  gameId: "game-456"
  videoId: "video-789"
  startTime: "0:10"
  endTime: "0:20"
  videoPath: "games/game-id/video-id_file.mp4"
  clipPath: "clips/test-123.mp4"
EOF

# Watch the ClipJob
kubectl get clipjobs -n film-review -w

# Watch the Job
kubectl get jobs -n film-review -w

# Check logs
kubectl logs -n film-review -l app=clip-processor -f
```

## Benefits Achieved

✅ **GPU Efficiency**: GPU only allocated when processing
✅ **Scalability**: Multiple clips process in parallel (up to 4 with time-slicing)
✅ **Fault Tolerance**: Automatic retries on failure
✅ **Observability**: Native Kubernetes status tracking
✅ **Resource Isolation**: Backend doesn't need GPU
✅ **Queue Management**: Kubernetes handles scheduling

## Next Steps

- Phase 2: Add priority queues
- Phase 3: Auto-scaling based on queue depth
- Phase 4: Multi-GPU support
- Phase 5: Clip quality selection (720p vs 1080p)

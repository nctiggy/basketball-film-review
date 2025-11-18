#!/usr/bin/env python3
"""
Basketball Film Review Clip Operator

This operator watches ClipJob custom resources and creates Kubernetes Jobs
to process video clips using ffmpeg with GPU acceleration.
"""
import kopf
import kubernetes
import logging
from datetime import datetime, timezone
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@kopf.on.create('filmreview.io', 'v1alpha1', 'clipjobs')
def create_clip_job(spec: Dict[str, Any], name: str, namespace: str, **kwargs):
    """
    Handle creation of ClipJob custom resource.
    Creates a Kubernetes Job to process the video clip.
    """
    logger.info(f"Creating clip job for ClipJob {namespace}/{name}")

    # Extract spec fields
    clip_id = spec['clipId']
    video_path = spec['videoPath']
    clip_path = spec['clipPath']
    start_time = spec['startTime']
    end_time = spec['endTime']
    minio_endpoint = spec.get('minioEndpoint', 'basketball-film-review-minio:9000')
    minio_secret = spec.get('minioSecretRef', {}).get('name', 'basketball-film-review-minio-credentials')
    ttl = spec.get('ttlSecondsAfterFinished', 3600)
    backoff_limit = spec.get('backoffLimit', 3)

    # Create Job name
    job_name = f"clip-{clip_id[:8]}"

    # Define the Job
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {
                "app": "clip-processor",
                "clipjob": name,
                "clip-id": clip_id,
            },
            "ownerReferences": [{
                "apiVersion": "filmreview.io/v1alpha1",
                "kind": "ClipJob",
                "name": name,
                "uid": kwargs['uid'],
                "controller": True,
                "blockOwnerDeletion": True,
            }],
        },
        "spec": {
            "ttlSecondsAfterFinished": ttl,
            "backoffLimit": backoff_limit,
            "template": {
                "metadata": {
                    "labels": {
                        "app": "clip-processor",
                        "clipjob": name,
                    }
                },
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [{
                        "name": "ffmpeg-processor",
                        "image": "nctiggy/clip-processor:latest",  # We'll build this next
                        "env": [
                            {"name": "CLIP_ID", "value": clip_id},
                            {"name": "VIDEO_PATH", "value": video_path},
                            {"name": "CLIP_PATH", "value": clip_path},
                            {"name": "START_TIME", "value": start_time},
                            {"name": "END_TIME", "value": end_time},
                            {"name": "MINIO_ENDPOINT", "value": minio_endpoint},
                            {"name": "MINIO_SECURE", "value": "false"},
                            {
                                "name": "MINIO_ACCESS_KEY",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": minio_secret,
                                        "key": "rootUser"
                                    }
                                }
                            },
                            {
                                "name": "MINIO_SECRET_KEY",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": minio_secret,
                                        "key": "rootPassword"
                                    }
                                }
                            },
                            {
                                "name": "DATABASE_URL",
                                "value": "postgresql://filmreview:filmreview@basketball-film-review-postgresql:5432/filmreview"
                            },
                        ],
                        "resources": {
                            "requests": {
                                "nvidia.com/gpu": "1",
                                "memory": "2Gi",
                                "cpu": "1000m",
                            },
                            "limits": {
                                "nvidia.com/gpu": "1",
                                "memory": "4Gi",
                                "cpu": "2000m",
                            }
                        },
                    }],
                    "nodeSelector": {
                        "kubernetes.io/hostname": "node13",  # GPU node
                    },
                }
            }
        }
    }

    # Create the Job
    api = kubernetes.client.BatchV1Api()
    try:
        api.create_namespaced_job(namespace=namespace, body=job)
        logger.info(f"Created Job {job_name} for ClipJob {name}")

        # Update ClipJob status
        return {
            'phase': 'Pending',
            'jobName': job_name,
            'startTime': datetime.now(timezone.utc).isoformat(),
        }
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to create Job: {e}")
        return {
            'phase': 'Failed',
            'message': f"Failed to create Job: {e}",
        }


@kopf.on.field('batch', 'v1', 'jobs', field='status.conditions', labels={'clipjob': kopf.PRESENT})
def job_status_changed(new, old, namespace, labels, **kwargs):
    """
    Watch for Job completion and update corresponding ClipJob status.
    Only watches Jobs with the 'clipjob' label (created by this operator).
    """
    # Only process jobs created by ClipJobs
    if not labels or 'clipjob' not in labels:
        return

    clipjob_name = labels['clipjob']

    # Check if job completed
    if new:
        for condition in new:
            if condition['type'] == 'Complete' and condition['status'] == 'True':
                logger.info(f"Job completed successfully for ClipJob {clipjob_name}")
                update_clipjob_status(namespace, clipjob_name, 'Succeeded')
            elif condition['type'] == 'Failed' and condition['status'] == 'True':
                logger.error(f"Job failed for ClipJob {clipjob_name}")
                reason = condition.get('reason', 'Unknown')
                message = condition.get('message', 'Job failed')
                update_clipjob_status(namespace, clipjob_name, 'Failed', message=f"{reason}: {message}")


def update_clipjob_status(namespace: str, name: str, phase: str, message: str = None):
    """Update ClipJob status"""
    api = kubernetes.client.CustomObjectsApi()

    status = {'phase': phase}
    if message:
        status['message'] = message
    if phase in ['Succeeded', 'Failed']:
        status['completionTime'] = datetime.now(timezone.utc).isoformat()
    elif phase == 'Running':
        status['startTime'] = datetime.now(timezone.utc).isoformat()

    try:
        api.patch_namespaced_custom_object_status(
            group='filmreview.io',
            version='v1alpha1',
            namespace=namespace,
            plural='clipjobs',
            name=name,
            body={'status': status}
        )
        logger.info(f"Updated ClipJob {name} status to {phase}")
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to update ClipJob status: {e}")


@kopf.on.delete('filmreview.io', 'v1alpha1', 'clipjobs')
def delete_clip_job(spec, name, namespace, **kwargs):
    """
    Handle deletion of ClipJob.
    The associated Job will be deleted automatically via ownerReferences.
    """
    logger.info(f"ClipJob {namespace}/{name} deleted")

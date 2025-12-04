#!/usr/bin/env python3
"""
Analysis Operator - Watches AnalysisJob CRDs and creates Kubernetes Jobs
to analyze basketball clips using configurable AI providers.

Supports multiple providers:
- gemini: Google Gemini (native video understanding) - default
- claude: Anthropic Claude (frame-by-frame analysis)
- qwen/replicate-qwen: Qwen2-VL via Replicate (native video)
"""

import kopf
import kubernetes
import logging
from datetime import datetime, timezone
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Kubernetes configuration
try:
    kubernetes.config.load_incluster_config()
except kubernetes.config.ConfigException:
    kubernetes.config.load_kube_config()


@kopf.on.create('filmreview.io', 'v1alpha1', 'analysisjobs')
def create_analysis_job(spec: Dict[str, Any], name: str, namespace: str, **kwargs):
    """
    Handle creation of AnalysisJob custom resource.
    Creates a Kubernetes Job to run the analysis worker.
    """
    logger.info(f"Creating analysis job for AnalysisJob {namespace}/{name}")

    # Extract spec fields
    clip_id = spec['clipId']
    game_id = spec['gameId']
    clip_path = spec['clipPath']
    home_team_color = spec['homeTeamColor']
    away_team_color = spec['awayTeamColor']
    fps = spec.get('framesPerSecond', 4.0)
    clip_notes = spec.get('clipNotes', '')

    # Provider selection - defaults to gemini for native video support
    provider = spec.get('provider', 'gemini')

    # Infrastructure config
    minio_endpoint = spec.get('minioEndpoint', 'minio:9000')
    minio_secret_ref = spec.get('minioSecretRef', {'name': 'basketball-film-review-minio-credentials'})
    anthropic_secret_ref = spec.get('anthropicSecretRef', {'name': 'anthropic-api-key'})
    google_secret_ref = spec.get('googleSecretRef', {'name': 'google-api-key'})
    replicate_secret_ref = spec.get('replicateSecretRef', {'name': 'replicate-api-token'})
    ttl_seconds = spec.get('ttlSecondsAfterFinished', 3600)
    backoff_limit = spec.get('backoffLimit', 2)

    # Create the Job spec
    job_name = f"analysis-{clip_id[:8]}"

    # Build environment variables based on provider
    env_vars = [
        {'name': 'CLIP_ID', 'value': clip_id},
        {'name': 'GAME_ID', 'value': game_id},
        {'name': 'CLIP_PATH', 'value': clip_path},
        {'name': 'HOME_TEAM_COLOR', 'value': home_team_color},
        {'name': 'AWAY_TEAM_COLOR', 'value': away_team_color},
        {'name': 'FRAMES_PER_SECOND', 'value': str(fps)},
        {'name': 'CLIP_NOTES', 'value': clip_notes},
        {'name': 'ANALYSIS_PROVIDER', 'value': provider},
        {'name': 'MINIO_ENDPOINT', 'value': minio_endpoint},
        {'name': 'MINIO_BUCKET', 'value': 'basketball-clips'},
        {
            'name': 'MINIO_ACCESS_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': minio_secret_ref['name'],
                    'key': 'rootUser'
                }
            }
        },
        {
            'name': 'MINIO_SECRET_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': minio_secret_ref['name'],
                    'key': 'rootPassword'
                }
            }
        },
        {'name': 'DATABASE_URL', 'value': 'postgresql://filmreview:filmreview@postgresql:5432/filmreview'}
    ]

    # Add provider-specific API keys
    if provider == 'claude':
        env_vars.append({
            'name': 'ANTHROPIC_API_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': anthropic_secret_ref['name'],
                    'key': 'api-key'
                }
            }
        })
    elif provider == 'gemini':
        env_vars.append({
            'name': 'GOOGLE_API_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': google_secret_ref['name'],
                    'key': 'api-key'
                }
            }
        })
    elif provider in ('qwen', 'replicate-qwen'):
        env_vars.append({
            'name': 'REPLICATE_API_TOKEN',
            'valueFrom': {
                'secretKeyRef': {
                    'name': replicate_secret_ref['name'],
                    'key': 'api-token'
                }
            }
        })

    job_manifest = {
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {
            'name': job_name,
            'namespace': namespace,
            'labels': {
                'analysisjob': name,
                'clip-id': clip_id[:8],
                'provider': provider
            },
            'ownerReferences': [{
                'apiVersion': 'filmreview.io/v1alpha1',
                'kind': 'AnalysisJob',
                'name': name,
                'uid': kwargs['body']['metadata']['uid'],
                'controller': True,
                'blockOwnerDeletion': True
            }]
        },
        'spec': {
            'ttlSecondsAfterFinished': ttl_seconds,
            'backoffLimit': backoff_limit,
            'template': {
                'metadata': {
                    'labels': {
                        'analysisjob': name,
                        'clip-id': clip_id[:8],
                        'provider': provider
                    }
                },
                'spec': {
                    'restartPolicy': 'Never',
                    'containers': [{
                        'name': 'analysis-worker',
                        'image': 'nctiggy/basketball-film-review-analysis-worker:latest',
                        'imagePullPolicy': 'Always',
                        'env': env_vars,
                        'resources': {
                            'requests': {
                                'memory': '512Mi',
                                'cpu': '250m'
                            },
                            'limits': {
                                'memory': '1Gi',
                                'cpu': '1000m'
                            }
                        }
                    }]
                }
            }
        }
    }

    # Create the Job
    batch_api = kubernetes.client.BatchV1Api()
    try:
        batch_api.create_namespaced_job(namespace=namespace, body=job_manifest)
        logger.info(f"Created Job {job_name} for AnalysisJob {name} (provider: {provider})")

        # Update status
        update_analysisjob_status(namespace, name, 'Pending', job_name=job_name)

    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:  # Already exists
            logger.warning(f"Job {job_name} already exists")
        else:
            logger.error(f"Failed to create Job: {e}")
            update_analysisjob_status(namespace, name, 'Failed', message=str(e))
            raise


@kopf.on.field('batch', 'v1', 'jobs', field='status.conditions', labels={'analysisjob': kopf.PRESENT})
def job_status_changed(new, old, namespace, labels, **kwargs):
    """
    Watch for Job completion and update corresponding AnalysisJob status.
    """
    if not labels or 'analysisjob' not in labels:
        return

    analysisjob_name = labels['analysisjob']

    if new:
        for condition in new:
            if condition['type'] == 'Complete' and condition['status'] == 'True':
                logger.info(f"Job completed successfully for AnalysisJob {analysisjob_name}")
                update_analysisjob_status(namespace, analysisjob_name, 'Succeeded')
            elif condition['type'] == 'Failed' and condition['status'] == 'True':
                logger.error(f"Job failed for AnalysisJob {analysisjob_name}")
                reason = condition.get('reason', 'Unknown')
                message = condition.get('message', 'Job failed')
                update_analysisjob_status(namespace, analysisjob_name, 'Failed', message=f"{reason}: {message}")


def update_analysisjob_status(namespace: str, name: str, phase: str, message: str = None, job_name: str = None):
    """Update AnalysisJob status"""
    api = kubernetes.client.CustomObjectsApi()

    status = {'phase': phase}
    if message:
        status['message'] = message
    if job_name:
        status['jobName'] = job_name
    if phase in ['Succeeded', 'Failed']:
        status['completionTime'] = datetime.now(timezone.utc).isoformat()
    elif phase == 'Running':
        status['startTime'] = datetime.now(timezone.utc).isoformat()

    try:
        api.patch_namespaced_custom_object_status(
            group='filmreview.io',
            version='v1alpha1',
            namespace=namespace,
            plural='analysisjobs',
            name=name,
            body={'status': status}
        )
        logger.info(f"Updated AnalysisJob {name} status to {phase}")
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Failed to update AnalysisJob status: {e}")


@kopf.on.delete('filmreview.io', 'v1alpha1', 'analysisjobs')
def delete_analysis_job(spec, name, namespace, **kwargs):
    """
    Handle deletion of AnalysisJob.
    The associated Job will be deleted automatically via ownerReferences.
    """
    logger.info(f"AnalysisJob {namespace}/{name} deleted")

#!/usr/bin/env python3
"""
Resubmit failed clips by creating ClipJobs for them.
This script queries the database for failed clips and creates ClipJob resources.
"""

import asyncio
import asyncpg
from kubernetes import client, config

# Database connection settings
DATABASE_URL = "postgresql://filmreview:filmreview@localhost:5432/filmreview"

async def main():
    # Load Kubernetes config
    config.load_kube_config(config_file="/Users/craigsmith/code/basketball-film-review/admin.app-eng.kubeconfig")
    custom_api = client.CustomObjectsApi()

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get all failed clips
        failed_clips = await conn.fetch("""
            SELECT
                c.id as clip_id,
                c.start_time,
                c.end_time,
                v.video_path
            FROM clips c
            JOIN videos v ON c.video_id = v.id
            WHERE c.status = 'failed'
            AND c.clip_path IS NULL
            ORDER BY c.created_at DESC
        """)

        print(f"Found {len(failed_clips)} failed clips to resubmit")

        for clip in failed_clips:
            clip_id = str(clip['clip_id'])
            video_path = clip['video_path']
            start_time = clip['start_time']
            end_time = clip['end_time']
            clip_path = f"clips/{clip_id}.mp4"

            print(f"\nResubmitting clip {clip_id}")
            print(f"  Video: {video_path}")
            print(f"  Time: {start_time} - {end_time}")

            # Create ClipJob resource
            clipjob = {
                "apiVersion": "filmreview.io/v1alpha1",
                "kind": "ClipJob",
                "metadata": {
                    "name": f"clip-{clip_id[:8]}",  # Shorten to avoid name length issues
                    "namespace": "film-review"
                },
                "spec": {
                    "clipId": clip_id,
                    "videoPath": video_path,
                    "clipPath": clip_path,
                    "startTime": start_time,
                    "endTime": end_time,
                    "ttlSecondsAfterFinished": 3600,
                    "backoffLimit": 3
                }
            }

            try:
                custom_api.create_namespaced_custom_object(
                    group="filmreview.io",
                    version="v1alpha1",
                    namespace="film-review",
                    plural="clipjobs",
                    body=clipjob
                )

                # Update clip status to pending
                await conn.execute(
                    "UPDATE clips SET status = 'pending', clip_path = $1 WHERE id = $2",
                    clip_path, clip['clip_id']
                )

                print(f"  ✓ Created ClipJob and updated status to pending")

            except client.exceptions.ApiException as e:
                print(f"  ✗ Error creating ClipJob: {e}")
                if "already exists" in str(e):
                    print(f"    ClipJob already exists, updating clip status anyway")
                    await conn.execute(
                        "UPDATE clips SET status = 'pending', clip_path = $1 WHERE id = $2",
                        clip_path, clip['clip_id']
                    )

        print(f"\n✓ Resubmitted {len(failed_clips)} clips")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

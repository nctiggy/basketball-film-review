#!/bin/bash
# Resubmit failed clips by creating ClipJobs with correct spec including gameId and videoId

export KUBECONFIG=${KUBECONFIG:-admin.app-eng.kubeconfig}

echo "Fetching failed clips from database..."

kubectl exec -n film-review basketball-film-review-postgresql-0 -- psql -U filmreview -d filmreview -t -c "
SELECT c.id, c.game_id, c.video_id, v.video_path, c.start_time, c.end_time
FROM clips c
JOIN videos v ON c.video_id = v.id
WHERE c.status = 'failed' AND c.clip_path IS NULL
ORDER BY c.created_at DESC;" | while IFS='|' read -r clip_id game_id video_id video_path start_time end_time; do

  # Trim whitespace
  clip_id=$(echo $clip_id | tr -d ' ')
  game_id=$(echo $game_id | tr -d ' ')
  video_id=$(echo $video_id | tr -d ' ')
  video_path=$(echo $video_path | tr -d ' ')
  start_time=$(echo $start_time | tr -d ' ')
  end_time=$(echo $end_time | tr -d ' ')

  if [ -n "$clip_id" ] && [ -n "$game_id" ] && [ -n "$video_id" ]; then
    clip_name="clip-${clip_id:0:8}"
    clip_path="clips/${clip_id}.mp4"

    echo ""
    echo "Creating ClipJob for clip $clip_id"
    echo "  Game: $game_id"
    echo "  Video: $video_id  "
    echo "  Time: $start_time - $end_time"

    # Create ClipJob with all required fields
    kubectl apply -f - <<EOF
apiVersion: filmreview.io/v1alpha1
kind: ClipJob
metadata:
  name: $clip_name
  namespace: film-review
spec:
  clipId: "$clip_id"
  gameId: "$game_id"
  videoId: "$video_id"
  videoPath: "$video_path"
  clipPath: "$clip_path"
  startTime: "$start_time"
  endTime: "$end_time"
  ttlSecondsAfterFinished: 3600
  backoffLimit: 3
EOF

    if [ $? -eq 0 ]; then
      # Update clip to pending status
      kubectl exec -n film-review basketball-film-review-postgresql-0 -- psql -U filmreview -d filmreview -c "UPDATE clips SET status = 'pending', clip_path = '$clip_path' WHERE id = '$clip_id';" > /dev/null
      echo "  ✓ Created ClipJob and updated status to pending"
    else
      echo "  ✗ Failed to create ClipJob"
    fi
  fi
done

echo ""
echo "✓ Resubmission complete"

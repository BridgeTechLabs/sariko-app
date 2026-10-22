#!/bin/bash
set -euo pipefail

IMAGE_REPO="sariko/sariko-backend"
CURRENT_TAG=$(cat /tmp/current_tag.txt)
PREVIOUS_TAG=$(cat /tmp/previous_tag.txt)

echo "Cleaning old images..."

docker images "$IMAGE_REPO" --format '{{.Repository}}:{{.Tag}}' |
while read -r IMAGE; do
    TAG="${IMAGE#"$IMAGE_REPO:"}"
    [[ $TAG == admin-* ]] && continue  # the admin panel's images share this repo; its pipeline manages them

    if [ "$TAG" = "$CURRENT_TAG" ] || [ "$TAG" = "$PREVIOUS_TAG" ]; then
        echo "Keeping $IMAGE"
    else
        echo "Removing $IMAGE"
        docker rmi "$IMAGE" || true
    fi
done

echo "Cleanup completed."

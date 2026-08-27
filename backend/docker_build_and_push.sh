#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE_TAG="${IMAGE_TAG:0:7}"

if [ -n "${DOCKERHUB_TOKEN:-}" ]; then
    echo "$DOCKERHUB_TOKEN" | docker login --username "${DOCKERHUB_USERNAME:-sariko}" --password-stdin
else
    cat src/envs/.docker-creds | docker login --username sariko --password-stdin
fi

docker build --platform linux/amd64 -t sariko-backend:$IMAGE_TAG .

# docker tag sariko-backend:$GIT_SHA sariko/sariko-backend:latest
docker tag sariko-backend:$IMAGE_TAG sariko/sariko-backend:$IMAGE_TAG

# docker push 
# docker push sariko/sariko-backend:latest
docker push sariko/sariko-backend:$IMAGE_TAG

docker logout
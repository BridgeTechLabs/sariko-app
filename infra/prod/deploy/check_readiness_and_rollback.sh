#!/bin/bash

echo "Waiting for application readiness..."
for i in {1..12}; do
	STATUS=$(docker inspect --format='{{.State.Health.Status}}' sariko-backend 2>/dev/null || echo "starting")
	
	echo "Attempt $i: $STATUS"
	
	if [ "$STATUS" = "healthy" ]; then
		echo "Application is healthy"
		exit 0
	fi

	sleep 5
done

echo "Application failed readiness check!"
export IMAGE_TAG=$(cat /tmp/previous_tag.txt)

echo "Rolling back to $IMAGE_TAG"
docker compose down
docker compose up -d

exit 1

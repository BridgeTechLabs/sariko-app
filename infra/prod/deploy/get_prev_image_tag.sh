#!/bin/bash

docker inspect --format='{{.Config.Image}}' sariko-backend | rev | cut -d: -f1 | rev > /tmp/previous_tag.txt
echo "$IMAGE_TAG" > /tmp/current_tag.txt

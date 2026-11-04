#!/bin/bash

docker run --rm \
    -v $(pwd)/nginx/certbot/conf:/etc/letsencrypt \
    -v $(pwd)/nginx/certbot/www:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d api.sariko.store \
    --email infra@sariko.store \
    --agree-tos \
    --no-eff-email

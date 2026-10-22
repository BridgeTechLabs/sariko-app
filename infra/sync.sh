#!/usr/bin/env bash
# Copy infra/<env>/ over ~ on that EC2 (paths under infra/<env>/ = paths under /home/ubuntu).
# Default is a dry run: lists the files that would change and diffs each one. --apply writes.
# Needs ssh aliases sariko-dev / sariko-prod in ~/.ssh/config. Same file in sariko-app and sariko-admin-panel.
set -euo pipefail
usage="usage: $0 <dev|prod> [--apply]"
env=${1:?$usage}
[[ $env == dev || $env == prod ]] || { echo "$usage"; exit 2; }
host=sariko-$env
src="$(cd "$(dirname "$0")" && pwd)/$env/"
# Never copy secrets or certificates, whatever .gitignore says. No --delete: files only on the server stay.
opts=(-rlci --exclude='.env*' --exclude='certbot/conf/')

if [[ ${2:-} != --apply ]]; then
    changed=$(rsync -n "${opts[@]}" "$src" "$host:")
    [[ -z $changed ]] && { echo "$env: no differences"; exit 0; }
    echo "$changed"
    awk '$1 ~ /^.f/ {print $2}' <<<"$changed" | while read -r f; do
        ssh -n "$host" "cat ~/$f 2>/dev/null" | diff -u --label "$host:~/$f" --label "infra/$env/$f" - "$src$f" || true
    done
    exit 0
fi

if [[ $env == prod ]]; then
    read -rp 'Writing to PROD. Type "prod" to continue: ' answer
    [[ $answer == prod ]] || { echo "aborted"; exit 1; }
fi

suffix=.bak-$(date +%Y%m%d-%H%M)
# --inplace keeps the inode: nginx.conf is a single-file bind mount.
changed=$(rsync "${opts[@]}" --inplace --backup --suffix="$suffix" "$src" "$host:")
echo "$changed"

if grep -q 'deploy/nginx/nginx.conf$' <<<"$changed"; then
    conf=deploy/nginx/nginx.conf
    if ssh "$host" 'docker exec nginx nginx -t && docker exec nginx nginx -s reload'; then
        echo "nginx reloaded"
    else
        echo "nginx -t failed: restoring $conf$suffix" >&2
        ssh "$host" "[ -f ~/$conf$suffix ] && cat ~/$conf$suffix > ~/$conf && docker exec nginx nginx -s reload"
        exit 1
    fi
fi

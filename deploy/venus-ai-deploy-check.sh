#!/usr/bin/env bash
set -euo pipefail

repo=/opt/venus-ai
cd "$repo"

git fetch --prune origin develop
local_commit="$(git rev-parse HEAD)"
remote_commit="$(git rev-parse origin/develop)"

if [[ "$local_commit" == "$remote_commit" ]]; then
  exit 0
fi

logger -t venus-ai-deploy "Novo commit em develop: $local_commit -> $remote_commit"
systemctl start venus-ai-deploy.service

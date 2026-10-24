#!/usr/bin/env bash

set -euo pipefail

: "${RENDER_DEPLOY_HOOK_URL:?Set RENDER_DEPLOY_HOOK_URL to the Render deploy hook (GitHub secret of the same name).}"

deploy_url="$RENDER_DEPLOY_HOOK_URL"
if [[ "${GITHUB_REF_TYPE:-}" == "tag" ]]; then
  : "${GITHUB_SHA:?GITHUB_SHA is required for a tagged release.}"
  deploy_url="${deploy_url}&ref=${GITHUB_SHA}"
fi

curl --fail --silent --show-error --request POST "$deploy_url" > /dev/null
echo "Render deploy started."

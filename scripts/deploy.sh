#!/usr/bin/env bash

set -euo pipefail

: "${RENDER_DEPLOY_HOOK_URL:?Set RENDER_DEPLOY_HOOK_URL to the Render deploy hook (GitHub secret of the same name).}"

curl --fail --silent --show-error --request POST "$RENDER_DEPLOY_HOOK_URL" > /dev/null
echo "Render deploy started."

#!/usr/bin/env bash
# Checks this machine's agent and environment setup. Safe to run any time.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

failures=0
ok()   { echo "✓ $1"; }
fail() { echo "✗ $1"; echo "    fix: $2"; failures=$((failures + 1)); }

linked=0
for dir in .agents .claude .cursor; do
  if [ -f "$dir/skills/ai-sdlc-0-bootstrap/SKILL.md" ]; then
    ok "$dir/skills resolves to the AI-SDLC skills"
    linked=1
  elif [ -e "$dir/skills" ] || [ -L "$dir/skills" ]; then
    fail "$dir/skills exists but does not contain the AI-SDLC skills" "remove it and run: bash scripts/setup-skills.sh"
  fi
done
[ "$linked" -eq 1 ] || fail "no agent can discover the skills" "bash scripts/setup-skills.sh all"

if [ -f CLAUDE.md ] && grep -q '@AGENTS.md' CLAUDE.md; then
  ok "CLAUDE.md imports AGENTS.md"
else
  fail "CLAUDE.md missing or does not import AGENTS.md" "bash scripts/setup-skills.sh claude"
fi

if [ -d environments/python ]; then
  if [ -x .venv/bin/python ] && .venv/bin/python -c "import sys" 2>/dev/null; then
    ok "Python environment in .venv"
  else
    fail "Python environment missing" "bash scripts/setup-python.sh"
  fi
fi

for f in docs/INDEX.json docs/TASKS.md docs/PROJECT.md; do
  [ -f "$f" ] && ok "$f present" || fail "$f missing" "restore it from the template"
done

echo ""
if [ "$failures" -eq 0 ]; then
  echo "Setup OK. Next: ask your agent to start BOOTSTRAP (see docs/TASKS.md)."
else
  echo "$failures setup problem(s) found."
  exit 1
fi

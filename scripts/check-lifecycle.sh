#!/usr/bin/env bash
# Checks that the AI-SDLC artefacts are present and consistent. Runs in CI.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

failures=0
fail() { echo "✗ $1"; failures=$((failures + 1)); }
warn() {
  echo "⚠ $1"
  if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::warning::$1"; fi
}

for f in AGENTS.md LICENSE docs/INDEX.json docs/TASKS.md docs/PROJECT.md \
         docs/STANDARDS.md docs/AGENT-GUIDANCE.md \
         docs/specs/UC-TEMPLATE.md docs/adr/ADR-TEMPLATE.md \
         .github/copilot-instructions.md; do
  [ -f "$f" ] || fail "missing $f"
done

if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  tracked=$(git ls-files | grep -E '(^|/)(\.venv|venv|__pycache__)/' || true)
  [ -z "$tracked" ] || fail "tracked environment/cache files: $(printf '%s\n' "$tracked" | head -3 | tr '\n' ' ')(remove with git rm -r --cached; see .gitignore)"
fi

for dir in skills/*/; do
  [ -f "${dir}SKILL.md" ] || fail "missing ${dir}SKILL.md"
  python3 -m json.tool "${dir}index.json" > /dev/null 2>&1 || fail "missing or invalid ${dir}index.json"
  python3 -c 'import json,sys; sys.exit(json.load(open(sys.argv[1])).get("model_tier") not in ("small","standard","large"))' "${dir}index.json" 2>/dev/null \
    || warn "${dir}index.json has no valid model_tier (small, standard or large); see CONTRIBUTING.md"
done

python3 - <<'PY' || failures=$((failures + 1))
import json, os, sys
try:
    index = json.load(open("docs/INDEX.json"))
except Exception as e:
    print(f"✗ docs/INDEX.json is not valid JSON: {e}")
    sys.exit(1)
paths = [p["skill"] for p in index["phases"]] + [p["instructions"] for p in index["phases"]]
paths += index["review_gated"]["paths"] + index["templates"]["paths"] + index["project"] + index["process"]
missing = [p for p in paths if not os.path.exists(p)]
for p in missing:
    print(f"✗ docs/INDEX.json references missing path {p}")
sys.exit(1 if missing else 0)
PY

phase=$(sed -n 's/^PHASE: *//p' docs/TASKS.md | head -1)
status=$(sed -n 's/^STATUS: *//p' docs/TASKS.md | head -1)
[[ "$phase" =~ ^[0-5]$ ]] || fail "docs/TASKS.md PHASE must be 0-5 (found '$phase')"
[[ "$status" =~ ^(ready|in-progress|done|blocked)$ ]] || fail "docs/TASKS.md STATUS must be ready, in-progress, done or blocked (found '$status')"

if [[ "$phase" =~ ^[1-5]$ ]] && grep -qF '[CHOOSE AT BOOTSTRAP]' LICENSE 2>/dev/null; then
  warn "LICENSE: the project licence is not chosen yet (section 2); choose one with the team"
fi

if [[ "$phase" =~ ^[1-5]$ ]] && grep -q 'TBD' docs/PROJECT.md; then
  fail "docs/PROJECT.md still contains TBD after BOOTSTRAP (PHASE $phase)"
fi

current_use_case=$(awk '/^## Current Use Case/{inside=1; next} inside && NF {gsub(/`/, ""); print; exit} /^## /{inside=0}' docs/TASKS.md)
if [[ "$phase" =~ ^[1-5]$ ]]; then
  if [[ -z "$current_use_case" || "$current_use_case" == *'UC-[NNN]-[NAME]'* || "$current_use_case" =~ ^Fast\ Track:[[:space:]]*$ ]]; then
    fail "docs/TASKS.md must name a concrete current use case (or 'Fast Track: <description>') after BOOTSTRAP"
  elif [[ "$current_use_case" =~ ^Fast\ Track: ]]; then
    :
  elif [ ! -f "$current_use_case" ]; then
    fail "docs/TASKS.md current use case does not exist: $current_use_case"
  fi
fi

if [ "$status" = "done" ]; then
  evidence=$(awk '/^## Evidence links/{inside=1; next} /^## /{inside=0} inside' docs/TASKS.md)
  acceptance=$(awk '/^## Acceptance \/ validation cues/{inside=1; next} /^## /{inside=0} inside' docs/TASKS.md)
  if [ -z "$(printf '%s' "$evidence" | sed '/^[[:space:]]*$/d')" ] || \
     printf '%s' "$evidence" | grep -Eq 'Link to the relevant|What artefact|What evidence'; then
    fail "STATUS: done requires concrete evidence links in docs/TASKS.md"
  fi
  if [ -z "$(printf '%s' "$acceptance" | sed '/^[[:space:]]*$/d')" ] || \
     printf '%s' "$acceptance" | grep -Eq 'What should be true|What evidence will show'; then
    fail "STATUS: done requires concrete acceptance or validation cues in docs/TASKS.md"
  fi
fi

if [[ "$phase" =~ ^[4-5]$ ]] && [ ! -f scripts/test.sh ]; then
  fail "scripts/test.sh is required from VALIDATE onward"
fi

grep -qF 'UC-[NNN]-[NAME]' docs/specs/UC-TEMPLATE.md \
  || fail "docs/specs/UC-TEMPLATE.md looks filled in (placeholder UC-[NNN]-[NAME] missing); restore it and copy it to a new UC file instead"
grep -qF 'ADR-[NNN]-[short-title]' docs/adr/ADR-TEMPLATE.md \
  || fail "docs/adr/ADR-TEMPLATE.md looks filled in (placeholder ADR-[NNN]-[short-title] missing); restore it and copy it to a new ADR file instead"

headings=$(grep '^## ' docs/specs/UC-TEMPLATE.md)
for uc in docs/specs/UC-*.md; do
  [ "$uc" = docs/specs/UC-TEMPLATE.md ] && continue
  [ -e "$uc" ] || continue
  while IFS= read -r h; do
    grep -qxF "$h" "$uc" || fail "$uc is missing section '$h'"
  done <<< "$headings"
done

for n in $(ls docs/specs/UC-[0-9]*.md 2>/dev/null | sed -E 's#.*/UC-([0-9]+)-.*#\1#' | sort | uniq -d); do
  fail "duplicate use-case number $n in docs/specs/; renumber before merging"
done
for n in $(ls docs/adr/ADR-[0-9]*.md 2>/dev/null | sed -E 's#.*/ADR-([0-9]+)-.*#\1#' | sort | uniq -d); do
  fail "duplicate ADR number $n in docs/adr/; renumber before merging"
done

if [ "$failures" -eq 0 ]; then
  echo "✓ AI-SDLC lifecycle checks passed"
else
  echo "$failures lifecycle problem(s) found."
  exit 1
fi

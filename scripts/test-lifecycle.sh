#!/usr/bin/env bash
# Scenario tests for scripts/check-lifecycle.sh. Each fixture sets its own
# lifecycle state, so results do not depend on the repository's current phase.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

failures=0
fail() {
  echo "✗ $1"
  failures=$((failures + 1))
}

BASE_DIR="$TEMP_DIR/base"
mkdir -p "$BASE_DIR"
rsync -a --exclude '.git' --exclude '.venv' "$ROOT_DIR/" "$BASE_DIR/"
printf '# PROJECT.md\n\nFixture project context.\n' > "$BASE_DIR/docs/PROJECT.md"
cp "$BASE_DIR/docs/specs/UC-TEMPLATE.md" "$BASE_DIR/docs/specs/UC-900-FIXTURE.md"

write_tasks() {
  local dir="$1" phase="$2" status="$3" use_case="$4" acceptance="$5" evidence="$6"
  cat > "$dir/docs/TASKS.md" <<EOF
# TASKS.md

PHASE: $phase
STATUS: $status

## Current Use Case

$use_case

## Acceptance / validation cues

$acceptance

## Evidence links

$evidence

## Next smallest step

Fixture step.
EOF
}

make_fixture() {
  local name="$1" phase="$2" status="$3" use_case="$4" acceptance="$5" evidence="$6"
  local dir="$TEMP_DIR/$name"
  cp -R "$BASE_DIR" "$dir"
  write_tasks "$dir" "$phase" "$status" "$use_case" "$acceptance" "$evidence"
  printf '%s\n' "$dir"
}

UC_OK='docs/specs/UC-900-FIXTURE.md'
UC_PLACEHOLDER='docs/specs/UC-[NNN]-[NAME].md'
ACCEPT_OK='- `scripts/test.sh` passes.'
EVIDENCE_OK='- `bash scripts/test.sh` — passed'
ACCEPT_PLACEHOLDER='- What should be true when this slice is done?'
EVIDENCE_PLACEHOLDER='- Link to the relevant spec, design note, test result, PR note, or review comment.'

set_project_licence_unchosen() {
  local dir="$1"
  printf '\nLicence: [CHOOSE AT BOOTSTRAP]\n' >> "$dir/LICENSE"
}

set_project_licence_chosen() {
  local dir="$1"
  sed -i '/\[CHOOSE AT BOOTSTRAP\]/d' "$dir/LICENSE"
}

expect_pass() {
  local label="$1" dir="$2"
  if ! bash "$dir/scripts/check-lifecycle.sh" > "$dir/check.out" 2>&1; then
    fail "$label should pass"
    sed 's/^/    /' "$dir/check.out"
  fi
}

expect_warn() {
  local label="$1" dir="$2" message="$3"
  if ! bash "$dir/scripts/check-lifecycle.sh" > "$dir/check.out" 2>&1; then
    fail "$label should pass with a warning, but failed"
    sed 's/^/    /' "$dir/check.out"
  elif ! grep -qF "$message" "$dir/check.out"; then
    fail "$label should warn (expected: $message)"
  fi
}

expect_no_warnings() {
  local label="$1" dir="$2"
  bash "$dir/scripts/check-lifecycle.sh" > "$dir/check.out" 2>&1
  if grep -q '^⚠' "$dir/check.out"; then
    fail "$label should have no warnings"
    sed 's/^/    /' "$dir/check.out"
  fi
}

expect_fail() {
  local label="$1" dir="$2" message="$3"
  if bash "$dir/scripts/check-lifecycle.sh" > "$dir/check.out" 2>&1; then
    fail "$label should fail"
  elif ! grep -qF "$message" "$dir/check.out"; then
    fail "$label failed for the wrong reason (expected: $message)"
    sed 's/^/    /' "$dir/check.out"
  fi
}

d=$(make_fixture bootstrap 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
expect_pass "BOOTSTRAP state with template placeholders" "$d"

d=$(make_fixture valid-validate 4 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
expect_pass "VALIDATE state with a concrete use case" "$d"

d=$(make_fixture placeholder-use-case 1 in-progress "$UC_PLACEHOLDER" "$ACCEPT_OK" "$EVIDENCE_OK")
expect_fail "placeholder current use case after BOOTSTRAP" "$d" "must name a concrete current use case"

d=$(make_fixture fast-track-entry 3 in-progress 'Fast Track: fix typo in login message' "$ACCEPT_OK" "$EVIDENCE_OK")
expect_pass "Fast Track entry instead of a use case after BOOTSTRAP" "$d"

d=$(make_fixture fast-track-empty 3 in-progress 'Fast Track:' "$ACCEPT_OK" "$EVIDENCE_OK")
expect_fail "Fast Track entry without a description" "$d" "must name a concrete current use case"

d=$(make_fixture missing-use-case 1 in-progress 'docs/specs/UC-999-MISSING.md' "$ACCEPT_OK" "$EVIDENCE_OK")
expect_fail "missing current use case file" "$d" "current use case does not exist"

d=$(make_fixture done-no-evidence 4 done "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_PLACEHOLDER")
expect_fail "done status with placeholder evidence" "$d" "requires concrete evidence links"

d=$(make_fixture done-no-acceptance 4 done "$UC_OK" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_OK")
expect_fail "done status with placeholder acceptance" "$d" "requires concrete acceptance"

d=$(make_fixture done-valid 4 done "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
expect_pass "done status with acceptance and evidence" "$d"

d=$(make_fixture no-test-script 4 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
rm "$d/scripts/test.sh"
expect_fail "VALIDATE without scripts/test.sh" "$d" "scripts/test.sh is required"

d=$(make_fixture develop-no-test-script 3 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
rm "$d/scripts/test.sh"
expect_pass "DEVELOP without scripts/test.sh" "$d"

d=$(make_fixture distinct-numbers 1 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
cp "$d/docs/specs/UC-900-FIXTURE.md" "$d/docs/specs/UC-901-OTHER.md"
cp "$d/docs/adr/ADR-TEMPLATE.md" "$d/docs/adr/ADR-901-other.md"
expect_pass "distinct use-case and ADR numbers" "$d"

d=$(make_fixture duplicate-uc 1 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
cp "$d/docs/specs/UC-900-FIXTURE.md" "$d/docs/specs/UC-900-OTHER.md"
expect_fail "duplicate use-case number" "$d" "duplicate use-case number 900"

d=$(make_fixture duplicate-adr 1 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
cp "$d/docs/adr/ADR-TEMPLATE.md" "$d/docs/adr/ADR-900-first.md"
cp "$d/docs/adr/ADR-TEMPLATE.md" "$d/docs/adr/ADR-900-second.md"
expect_fail "duplicate ADR number" "$d" "duplicate ADR number 900"

d=$(make_fixture index-missing-path 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
rm "$d/scripts/sdlc.py"
expect_fail "INDEX.json lists a review-gated path that is missing" "$d" "docs/INDEX.json references missing path scripts/sdlc.py"

d=$(make_fixture index-missing-template 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
rm "$d/docs/adr/ADR-TEMPLATE.md"
expect_fail "INDEX.json lists a template that is missing" "$d" "docs/INDEX.json references missing path docs/adr/ADR-TEMPLATE.md"

d=$(make_fixture uc-template-filled 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
sed -i 's/UC-\[NNN\]-\[NAME\]/UC-007-LOGIN/' "$d/docs/specs/UC-TEMPLATE.md"
expect_fail "filled-in use-case template" "$d" "docs/specs/UC-TEMPLATE.md looks filled in"

d=$(make_fixture adr-template-filled 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
sed -i 's/ADR-\[NNN\]-\[short-title\]/ADR-004-database/' "$d/docs/adr/ADR-TEMPLATE.md"
expect_fail "filled-in ADR template" "$d" "docs/adr/ADR-TEMPLATE.md looks filled in"

d=$(make_fixture no-license 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
rm "$d/LICENSE"
expect_fail "missing LICENSE (CC BY 4.0 attribution)" "$d" "missing LICENSE"

d=$(make_fixture license-unchosen-after-bootstrap 1 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
set_project_licence_unchosen "$d"
expect_warn "project licence not chosen after BOOTSTRAP" "$d" "LICENSE: the project licence is not chosen yet"

d=$(make_fixture license-chosen 1 in-progress "$UC_OK" "$ACCEPT_OK" "$EVIDENCE_OK")
set_project_licence_chosen "$d"
expect_no_warnings "project licence chosen" "$d"

d=$(make_fixture tiers-present 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
expect_no_warnings "every skill declares model_tier" "$d"

d=$(make_fixture tier-missing 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
sed -i '/"model_tier"/d' "$d/skills/ai-sdlc-3-develop/index.json"
expect_warn "skill without model_tier" "$d" "skills/ai-sdlc-3-develop/index.json has no valid model_tier"

d=$(make_fixture tier-invalid 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
sed -i 's/"model_tier": "[a-z]*"/"model_tier": "huge"/' "$d/skills/ai-sdlc-3-develop/index.json"
expect_warn "skill with invalid model_tier" "$d" "skills/ai-sdlc-3-develop/index.json has no valid model_tier"

git_fixture() {
  local dir="$1"
  git -C "$dir" init -q
  git -C "$dir" add -A
}

d=$(make_fixture tracked-clean 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
git_fixture "$d"
expect_pass "git work tree without environment or cache files" "$d"

d=$(make_fixture tracked-venv 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
mkdir -p "$d/.venv/bin" && : > "$d/.venv/bin/python"
git_fixture "$d"
git -C "$d" add -f .venv/bin/python
expect_fail "committed .venv" "$d" "tracked environment/cache files"

d=$(make_fixture tracked-pycache 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
mkdir -p "$d/pkg/__pycache__" && : > "$d/pkg/__pycache__/x.pyc"
git_fixture "$d"
git -C "$d" add -f pkg/__pycache__/x.pyc
expect_fail "committed __pycache__" "$d" "tracked environment/cache files"

d=$(make_fixture ignored-venv 0 ready "$UC_PLACEHOLDER" "$ACCEPT_PLACEHOLDER" "$EVIDENCE_PLACEHOLDER")
mkdir -p "$d/.venv/bin" && : > "$d/.venv/bin/python"
git_fixture "$d"
expect_pass "untracked, ignored .venv" "$d"

if [ "$failures" -eq 0 ]; then
  echo "✓ lifecycle scenario tests passed"
else
  echo "$failures lifecycle scenario test(s) failed."
  exit 1
fi

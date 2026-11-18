#!/bin/bash
# Verifier: apply hidden tests, run fail-to-pass + pass-to-pass, write reward.
set -uo pipefail
mkdir -p /logs/verifier /logs/artifacts
cd /app || { echo 0 > /logs/verifier/reward.txt; exit 0; }

# Save what the agent changed (useful for review).
git add -A && git diff --cached --binary > /logs/artifacts/model.patch || true
git reset -q

# Undo any agent edits to files the hidden test patch touches.
grep -E '^diff --git ' /tests/test.patch | sed -E 's#^diff --git a/.* b/##' | while read -r f; do
  git checkout -q HEAD -- "$f" 2>/dev/null || rm -f "$f"
done

# Hidden tests the agent never saw. Harbor copies tests/ to /tests at verify time.
if ! git apply --whitespace=nowarn /tests/test.patch; then
  echo "[verifier] test.patch did not apply"
  echo 0 > /logs/verifier/reward.txt; exit 0
fi

# 1) FAIL_TO_PASS: tests that fail on the base commit and must pass after the fix.
FAIL_TO_PASS="com.example.FooTest#handlesEdgeCase+rejectsInvalid,com.example.BarTest"
# 2) PASS_TO_PASS: existing tests that must keep passing (regressions).
PASS_TO_PASS="com.example.FooTest,com.example.BazTest"

ok=1
mvn -q -B test -Dtest="$FAIL_TO_PASS" -Dsurefire.failIfNoSpecifiedTests=false || ok=0
mvn -q -B test -Dtest="$PASS_TO_PASS" -Dsurefire.failIfNoSpecifiedTests=false || ok=0

echo "$ok" > /logs/verifier/reward.txt
echo "[verifier] reward=$ok"
exit 0

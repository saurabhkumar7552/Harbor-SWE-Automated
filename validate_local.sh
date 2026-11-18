#!/bin/bash
# Manual oracle/nop validation without the harbor CLI.
# Usage: ./validate_local.sh tasks/<task-id> [image-tag]
#   nop    : run tests/test.sh on the untouched base commit  -> reward must be 0
#   oracle : run solution/solve.sh, then tests/test.sh        -> reward must be 1
set -uo pipefail
TASK="$(cd "$1" && pwd)"
IMG="${2:-task-$(basename "$TASK")}"
# Git Bash on Windows: hand Docker a Windows path (F:/...) and stop MSYS from rewriting
# container paths like /tests. On Linux/WSL cygpath doesn't exist and the path is used as is.
if command -v cygpath >/dev/null 2>&1; then
  TASK="$(cygpath -m "$TASK")"
fi
export MSYS_NO_PATHCONV=1

docker image inspect "$IMG" >/dev/null 2>&1 || docker build -t "$IMG" "$TASK/environment" || exit 1

run() {  # $1 = nop|oracle
  local mode=$1 cmd
  if [ "$mode" = oracle ]; then
    cmd='bash /solution/solve.sh && bash /tests/test.sh'
  else
    cmd='bash /tests/test.sh'
  fi
  docker run --rm \
    -v "$TASK/tests:/tests:ro" -v "$TASK/solution:/solution:ro" \
    "$IMG" bash -c "$cmd; echo \"[validate] $mode reward=\$(cat /logs/verifier/reward.txt)\""
}

run nop    2>&1 | tail -n 40
run oracle 2>&1 | tail -n 40

#!/bin/bash
# Single entry point for the task factory, so one narrow permission rule can cover it:
#   Bash(bash harbor_pipeline/factory/run.sh:*)
# Works from Git Bash on Windows (re-runs itself inside WSL Ubuntu) and from WSL directly.
#
#   bash harbor_pipeline/factory/run.sh <repo> status
#   bash harbor_pipeline/factory/run.sh <repo> propose <count>        # scout + review + revise only
#   bash harbor_pipeline/factory/run.sh <repo> package <task_id>      # build -> final gate for one task
#   bash harbor_pipeline/factory/run.sh <repo> package-all            # build -> final gate for all unfinished
#   bash harbor_pipeline/factory/run.sh <repo> eval <task_id>         # Sol eval + learn + verdict (reject easy / report) for one task
#   bash harbor_pipeline/factory/run.sh <repo> gate <task_id>         # deterministic gate only
#   bash harbor_pipeline/factory/run.sh <repo> research               # refresh the web research brief (propose does it when stale)
#   bash harbor_pipeline/factory/run.sh <repo> instruction-check <task_id>  # leak check/rewrite of a packaged task (no Docker; next package run re-gates a rewrite)
set -euo pipefail

if ! grep -qi microsoft /proc/version 2>/dev/null; then
  # Git Bash on Windows: hand over to WSL without MSYS rewriting the /mnt path
  MSYS_NO_PATHCONV=1 exec wsl -d Ubuntu -- bash /mnt/f/GITHUB/DataOrigin_SWE/harbor_pipeline/factory/run.sh "$@"
fi

cd "$(dirname "$0")"
repo=${1:?repo profile, e.g. hoppscotch}
action=${2:?action: status|propose|package|package-all|eval|gate|research|instruction-check}
shift 2

case "$repo" in *[!a-z0-9_-]*) echo "bad repo name"; exit 2 ;; esac
case "${1:-}" in *[!a-z0-9-]*) echo "bad argument"; exit 2 ;; esac

F=(python3 factory.py --repo "$repo")
case "$action" in
  status)      "${F[@]}" status ;;
  propose)     "${F[@]}" run --count "${1:?count}" --until proposal ;;
  package)     "${F[@]}" run --resume --until package --only "${1:?task_id}" ;;
  package-all) "${F[@]}" run --resume --until package ;;
  eval)        "${F[@]}" run --resume --eval --only "${1:?task_id}" ;;
  gate)        "${F[@]}" gate "${1:?task_id}" ;;
  research)    "${F[@]}" research ;;
  instruction-check) "${F[@]}" instruction-check "${1:?task_id}" ;;
  *) echo "unknown action: $action"; exit 2 ;;
esac

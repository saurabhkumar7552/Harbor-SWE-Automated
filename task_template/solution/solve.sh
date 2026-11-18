#!/bin/bash
# Reference solution used by the oracle agent (`-a oracle`) to prove the task is solvable.
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch

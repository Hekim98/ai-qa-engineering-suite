#!/bin/zsh
set -e

cd -- "${0:A:h}/.."

if [[ ! -x .venv/bin/ai-qa ]]; then
  echo "AI QA Engineering Suite is not installed in .venv yet."
  echo "Complete the Local setup steps in README.md, then open this file again."
  read -r "?Press Return to close."
  exit 1
fi

.venv/bin/ai-qa dashboard

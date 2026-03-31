#!/bin/bash

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

case "$FILE_PATH" in
  *.js|*.jsx|*.ts|*.tsx|*.json|*.css|*.md)
    npx prettier --write "$FILE_PATH" 2>/dev/null
    ;;
  *.py)
    ruff format "$FILE_PATH" 2>/dev/null
    ;;
esac

exit 0
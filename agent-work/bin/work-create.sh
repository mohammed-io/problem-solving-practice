#!/bin/bash

# Script to create new work in progress files

WORK_DIR="agent-work"

name="$1"

if [ -z "$name" ]; then
  echo "Usage: work-create <name>"
  echo "Example: work-create improve_pdf_generation"
  exit 1
fi

# Generate timestamp in UTC
timestamp=$(TZ=UTC date +"%Y%m%d%H%M%S")

# Create filename
filename="${timestamp}_${name}.md"
filepath="$WORK_DIR/$filename"

# Create the work file with template
cat > "$filepath" <<EOF
# ${name}

## Status: in_progress

## Context
Context of this feature

## Value Proposition
What it tries to solve

## Alternatives considered
Other options

## Todos
- [ ] Task 1

## Notes
EOF

echo "Created work file: $filepath"

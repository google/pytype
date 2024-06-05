#!/bin/bash -e
set -o pipefail

# Launch the kythe browser

BROWSE_PORT="${BROWSE_PORT:-8080}"

# The easiest way to install kythe is as user in your home directory.
KYTHE_HOME="$HOME/kythe"
KYTHE_TOOLS="$KYTHE_HOME/tools"

# Convert the graphstore to serving tables.
$KYTHE_TOOLS/write_tables -graphstore graphstore -out=tables

# Host the browser UI.
$KYTHE_TOOLS/http_server -serving_table tables \
  -public_resources="${KYTHE_HOME}/web/ui" \
  -listen="localhost:${BROWSE_PORT}"

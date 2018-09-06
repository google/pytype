#!/bin/bash -e
set -o pipefail
BROWSE_PORT="${BROWSE_PORT:-8080}"

# The easiest way to install kythe is as user in your home directory.
KYTHE_HOME="$HOME/kythe"
KYTHE_TOOLS="$KYTHE_HOME/tools"

# You can find prebuilt binaries at https://github.com/google/kythe/releases.
# This script assumes that they are installed to $HOME/kythe.
# If you build the tools yourself or install them to a different location,
# make sure to pass the correct public_resources directory to http_server.
rm -f -- graphstore/* tables/*
mkdir -p graphstore tables
# Read JSON entries from standard in to a graphstore.
$KYTHE_TOOLS/entrystream --read_format=json \
  | $KYTHE_TOOLS/write_entries -graphstore graphstore
# Convert the graphstore to serving tables.
$KYTHE_TOOLS/write_tables -graphstore graphstore -out=tables
# Host the browser UI.
$KYTHE_TOOLS/http_server -serving_table tables \
  -public_resources="${KYTHE_HOME}/web/ui" \
  -listen="localhost:${BROWSE_PORT}"

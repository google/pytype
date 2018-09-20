#!/bin/bash -e
set -o pipefail

# Add a file's graph entries to the kythe index.
# Usage:
#   xref file | kythe-add-index.sh

# The easiest way to install kythe is as user in your home directory.
KYTHE_HOME="$HOME/kythe"
KYTHE_TOOLS="$KYTHE_HOME/tools"

# Read JSON entries from standard in to a graphstore.
$KYTHE_TOOLS/entrystream --read_format=json \
  | $KYTHE_TOOLS/write_entries -graphstore graphstore

#!/bin/bash -e
set -o pipefail

# Run the kythe verifier
# Usage:
#   xref <file> | kythe-verifier.sh <file>

# The easiest way to install kythe is as user in your home directory.
KYTHE_HOME="$HOME/kythe"
KYTHE_TOOLS="$KYTHE_HOME/tools"

# Read JSON entries from standard in and pass them to the verifier.
$KYTHE_TOOLS/entrystream --read_format=json \
  | $KYTHE_TOOLS/verifier --goal_prefix="#-" "$@"

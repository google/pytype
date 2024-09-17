#!/bin/sh

set -e -x

# Lint
pylint build_scripts pytype pytype_extensions setup.py -j 0

# Build
python build_scripts/build.py

# Run Tests
python build_scripts/run_tests.py -f -v

# Type Check
python out/bin/pytype -j auto

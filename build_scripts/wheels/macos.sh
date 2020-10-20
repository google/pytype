#!/bin/bash

set -eux

brew untap local/openssl
brew untap local/python2
brew update
python -V
brew install -v bison || brew upgrade bison
brew install -v cmake || brew upgrade cmake
brew install -v ninja || brew upgrade ninja
python -m pip install -U pip setuptools wheel
CMAKE_PREFIX_PATH="$(brew --prefix bison)"
export CMAKE_PREFIX_PATH
python -m pip wheel . --verbose --no-deps -w dist

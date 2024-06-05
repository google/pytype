#!/bin/bash

set -eux

brew update
python -V
brew install -v bison || brew upgrade bison
brew install -v cmake || brew upgrade cmake
# temporary workaround for https://github.com/actions/virtual-environments/issues/2428
rm -rf /usr/local/bin/2to3
brew install -v ninja || brew upgrade ninja
python -m pip install -U pip setuptools wheel
CMAKE_PREFIX_PATH="$(brew --prefix bison)"
export CMAKE_PREFIX_PATH
python -m pip wheel . --verbose --no-deps -w dist

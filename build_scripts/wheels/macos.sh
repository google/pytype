#!/bin/bash

set -eux

brew update
brew upgrade pyenv
eval "$(pyenv init -)"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
pyenv --version
pyenv install -s "$PYENV_VERSION"
pyenv local "$PYENV_VERSION"
python -V
brew install -v bison || brew upgrade bison
brew install -v cmake || brew upgrade cmake
brew install -v ninja || brew upgrade ninja
python -m pip install -U pip setuptools wheel
export CMAKE_PREFIX_PATH="$(brew --prefix bison)"
python -m pip wheel . --verbose --no-deps -w macos-wheelhouse

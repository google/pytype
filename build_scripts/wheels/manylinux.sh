#!/bin/bash

set -eux

if [[ -z "$PLAT" ]]; then
  # Early check, don't wait for -u to catch it later
  echo "Specify non-empty PLAT variable" >&2
  exit 1
fi

dnf install -y ninja-build python3-devel flex bison
cd /io
dirs -c

cmake --version
ninja --version
flex --version
bison --version

rm -rvf linux-wheelhouse
for tag in $PYTHON_TAGS; do
  PYBIN="/opt/python/${tag}/bin"
  rm -rvf out/CMake* CMakeCache.txt cmake_install.cmake build.ninja rules.ninja
  "${PYBIN}/python" -m pip install -U pip setuptools wheel
  "${PYBIN}/python" -m pip wheel . --no-deps -w linux-wheelhouse
done

for whl in linux-wheelhouse/*.whl; do
  auditwheel repair "$whl" --plat "$PLAT" -w linux-wheelhouse/
  rm -f "$whl"
done

mkdir dist
mv linux-wheelhouse/*.whl dist/

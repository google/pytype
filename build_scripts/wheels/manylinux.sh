#!/bin/bash

set -eux

if [[ -z "$PLAT" ]]; then
  # Early check, don't wait for -u to catch it later
  echo "Specify non-empty PLAT variable" >&2
  exit 1
fi

yum install -y gettext-devel python3-devel # gettext is for flex

# TODO: what should be the update cadence for these?
NINJA_VERSION='1.10.0'
BISON_VERSION='3.6'
FLEX_VERSION='2.6.4'

untar() {
  mkdir -pv "$1"
  tar -C "$1" -xzvf "${1}.tar.gz" --strip-components=1
  rm -vf "${1}.tar.gz"
}

# Install ninja/ninja-build (requires CMake)
curl -sSL \
  -o ninja.zip \
  "https://github.com/ninja-build/ninja/releases/download/v${NINJA_VERSION}/ninja-linux.zip"
unzip ninja.zip
mv ninja /usr/local/bin/
rm -vf ninja*
ln -s /usr/local/bin/ninja /usr/local/bin/ninja-build

TD="$(mktemp -d)"
pushd "$TD" || exit 1

# Install Flex
curl -sSL \
  -o flex.tar.gz \
  "https://github.com/westes/flex/releases/download/v${FLEX_VERSION}/flex-${FLEX_VERSION}.tar.gz"
untar flex
pushd flex
./autogen.sh && ./configure && make && make install
popd

# Install GNU Bison
curl -sSL \
  -o bison.tar.gz \
  "https://ftp.gnu.org/gnu/bison/bison-${BISON_VERSION}.tar.gz"
untar bison
pushd bison
./configure && make && make install

cd /io
dirs -c
rm -rf "$TD"

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

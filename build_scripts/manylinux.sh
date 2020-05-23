#!/bin/bash
#
# N.B.: This is a work-in-progress/broken/one-off/incomplete

yum update -y
yum install -y \
    cmake \
    gettext \
    gettext-devel \
    ninja-build

BISON_VERSION='3.6'
FLEX_VERSION='2.6.4'
PY_VERSIONS='cp35 cp36 cp37'

TD="$(mktemp -d)"
pushd "$TD" || exit 1
mkdir -pv {bison,flex}

curl -sSL \
    -o bison.tar.gz \
    "https://ftp.gnu.org/gnu/bison/bison-${BISON_VERSION}.tar.gz"
tar -C bison -xzvf bison.tar.gz --strip-components=1
rm -f bison.tar.gz
pushd bison
./configure && make && make install
popd

curl -sSL \
    -o flex.tar.gz \
    "https://github.com/westes/flex/releases/download/v${FLEX_VERSION}/flex-${FLEX_VERSION}.tar.gz"
tar -C flex -xzvf flex.tar.gz --strip-components=1
rm -f flex.tar.gz
pushd flex
./autogen.sh
./configure && make && make install
popd
popd
rm -rf "$TD"

bison --version
flex --version

# https://cmake.org/cmake/help/v3.0/module/FindPythonLibs.html
# https://github.com/Kitware/CMake/blob/master/Modules/FindPythonLibs.cmake
# PYTHON_INCLUDE_DIR='/opt/_internal/cpython-3.8.3/include/python3.8' PYTHON_LIBRARY='/opt/_internal/cpython-3.8.3/lib'
cd /io
/opt/python/cp37-cp37m/bin/python setup.py bdist_wheel --no-deps

# for PYBIN in /opt/python/*/bin; do
#     # TODO: version check
#     "${PYBIN}/python" -m pip install -U auditwheel
#     "${PYBIN}/python" /io/setup.py bdist_wheel --no-deps -w wheelhouse/
# done

# https://github.com/pypa/manylinux/blob/master/docker/build_scripts/build.sh
PYTHON_COMPILE_DEPS='zlib-devel bzip2-devel expat-devel ncurses-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel'

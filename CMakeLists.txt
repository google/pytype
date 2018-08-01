project(PyType)
# The minimum CMake version is currently governed by the CMake version that can
# be installed on the Travis Trusty VMs with apt-get.
cmake_minimum_required(VERSION 2.8)

set(CMAKE_MODULE_PATH
  "${CMAKE_MODULE_PATH}"
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules"
)
include(PyTypeUtils)

set(PYTYPE_OUT_BIN_DIR ${PROJECT_BINARY_DIR}/bin)
file(MAKE_DIRECTORY ${PYTYPE_OUT_BIN_DIR})

add_subdirectory(pytype)

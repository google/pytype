# The version in Ubuntu 20.04:
cmake_minimum_required(VERSION 3.16)
cmake_policy(SET CMP0148 OLD)

project(PyType)

set(CMAKE_CXX_STANDARD 20)

if (WIN32)
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
ENDIF()

set(CMAKE_MODULE_PATH
  "${CMAKE_MODULE_PATH}"
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules"
)
include(PyTypeUtils)

set(PYTYPE_OUT_BIN_DIR ${PROJECT_BINARY_DIR}/bin)
file(MAKE_DIRECTORY ${PYTYPE_OUT_BIN_DIR})

add_subdirectory(pybind11)
add_subdirectory(pytype)
add_subdirectory(pytype_extensions)
add_subdirectory(third_party)

# Add the "googletest" directory at the end as it defines its own CMake rules
# for py_test etc. Adding it at the end avoids mixing up Pytype's definitions
# with these definitions.
add_subdirectory(googletest)

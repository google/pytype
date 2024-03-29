project(PyType)
# The minimum CMake version is currently governed by the CMake version that can
# be installed on the Travis Trusty VMs with apt-get.
cmake_minimum_required(VERSION 2.8)

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

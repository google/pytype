project(PyType)
cmake_minimum_required(VERSION 3.4)

set(CMAKE_MODULE_PATH
  "${CMAKE_MODULE_PATH}"
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules"
)
include(PyTypeUtils)

add_subdirectory(pytype)

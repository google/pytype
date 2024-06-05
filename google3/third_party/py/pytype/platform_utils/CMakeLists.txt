add_package()

py_library(
  NAME
    platform_utils
  DEPS
    .init
    .path_utils
    .tempfile
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_library(
  NAME
    path_utils
  SRCS
    path_utils.py
)

py_library(
  NAME
    tempfile
  SRCS
    tempfile.py
  DEPS
    .path_utils
)

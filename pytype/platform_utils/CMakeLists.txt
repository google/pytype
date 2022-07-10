add_package()

py_library(
  NAME
    platform_utils
  DEPS
    .path_utils
    .tempfile
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

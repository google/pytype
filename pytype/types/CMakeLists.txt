add_package()

py_library(
  NAME
    types
  DEPS
    ._types
)

py_library(
  NAME
    _types
  SRCS
    types.py
  DEPS
    .base
    .classes
    .functions
)

py_library(
  NAME
    base
  SRCS
    base.py
  DEPS
    pytype.pytd.pytd
)

py_library(
  NAME
    classes
  SRCS
    classes.py
  DEPS
    .base
    .functions
)

py_library(
  NAME
    functions
  SRCS
    functions.py
  DEPS
    .base
)

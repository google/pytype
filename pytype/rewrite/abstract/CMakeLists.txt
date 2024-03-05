add_package()

py_library(
  NAME
    abstract
  SRCS
    abstract.py
  DEPS
    .base
    .classes
    .functions
    .utils
)

py_library(
  NAME
    base
  SRCS
    base.py
  DEPS
    pytype.rewrite.flow.flow
)

py_test(
  NAME
    base_test
  SRCS
    base_test.py
  DEPS
    .base
    pytype.rewrite.flow.flow
)

py_library(
  NAME
    classes
  SRCS
    classes.py
  DEPS
    .base
)

py_library(
  NAME
    functions
  SRCS
    functions.py
  DEPS
    .base
    pytype.blocks.blocks
)

py_library(
  NAME
    utils
  SRCS
    utils.py
  DEPS
    .base
    pytype.rewrite.flow.flow
)

py_test(
  NAME
    utils_test
  SRCS
    utils_test.py
  DEPS
    .base
    .utils
)

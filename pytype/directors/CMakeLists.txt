add_package()

py_library(
  NAME
    directors
  DEPS
    ._directors
    .annotations
    .init
    .parser
)

py_library(
  NAME
    _directors
  SRCS
    directors.py
  DEPS
    .annotations
    .parser
    pytype.config
)

py_library(
  NAME
    annotations
  SRCS
    annotations.py
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_library(
  NAME
    parser
  SRCS
    parser.py
  DEPS
    pytype.ast.ast
)

py_test(
  NAME
    directors_test
  SRCS
    directors_test.py
  DEPS
    .directors
    pytype.errors.errors
    pytype.tests.test_utils
)

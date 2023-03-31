add_package()

py_library(
  NAME
    blocks
  SRCS
    blocks.py
  DEPS
    pytype.pyc.pyc
    pytype.typegraph.cfg_utils
)

py_library(
  NAME
    block_serializer
  SRCS
    block_serializer.py
  DEPS
    .blocks
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_test(
  NAME
    blocks_test
  SRCS
    blocks_test.py
  DEPS
    .blocks
    pytype.directors.annotations
    pytype.pyc.pyc
    pytype.tests.test_base
)

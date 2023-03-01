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
    pytype.pyc.pyc
    pytype.tests.test_base
)

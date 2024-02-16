add_package()

py_library(
  NAME
    test_utils
  SRCS
    test_utils.py
  DEPS
    pytype.blocks.blocks
    pytype.pyc.pyc
    pytype_extensions.instrumentation_for_testing
)

add_package()

py_library(
  NAME
    overlays
  DEPS
    .special_builtins
)

py_library(
  NAME
    special_builtins
  SRCS
    special_builtins.py
  DEPS
    pytype.rewrite.abstract.abstract
)

py_test(
  NAME
    special_builtins_test
  SRCS
    special_builtins_test.py
  DEPS
    .special_builtins
    pytype.rewrite.abstract.abstract
    pytype.rewrite.abstract.test_utils
)

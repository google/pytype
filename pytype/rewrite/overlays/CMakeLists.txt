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
    pytype.rewrite.pretty_printer
    pytype.rewrite.abstract.abstract
)

py_test(
  NAME
    special_builtins_test
  SRCS
    special_builtins_test.py
  DEPS
    .special_builtins
    pytype.rewrite.context
    pytype.rewrite.abstract.abstract
)

add_package()

py_library(
  NAME
    overlays
  DEPS
    ._overlays
    .enum_overlay
    .special_builtins
)

py_library(
  NAME
    _overlays
  SRCS
    overlays.py
  DEPS
    pytype.rewrite.abstract.abstract
)

py_library(
  NAME
    enum_overlay
  SRCS
    enum_overlay.py
  DEPS
    ._overlays
    pytype.rewrite.abstract.abstract
)

py_library(
  NAME
    special_builtins
  SRCS
    special_builtins.py
  DEPS
    ._overlays
    pytype.rewrite.abstract.abstract
)

py_test(
  NAME
    special_builtins_test
  SRCS
    special_builtins_test.py
  DEPS
    pytype.rewrite.abstract.abstract
    pytype.rewrite.tests.test_utils
)

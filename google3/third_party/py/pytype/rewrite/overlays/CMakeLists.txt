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

py_test(
  NAME
    overlays_test
  SRCS
    overlays_test.py
  DEPS
    ._overlays
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

py_test(
  NAME
    enum_overlay_test
  SRCS
    enum_overlay_test.py
  DEPS
    .enum_overlay
    pytype.rewrite.abstract.abstract
    pytype.rewrite.tests.test_utils
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

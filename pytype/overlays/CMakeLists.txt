add_package()

py_library(
  NAME
    classgen
  SRCS
    classgen.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    abc_overlay
  SRCS
    abc_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    asyncio_types_overlay
  SRCS
    asyncio_types_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    attr_overlay
  SRCS
    attr_overlay.py
  DEPS
    .classgen
    pytype.libvm
)

py_library(
  NAME
    collections_overlay
  SRCS
    collections_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    dataclass_overlay
  SRCS
    dataclass_overlay.py
  DEPS
    .classgen
    pytype.libvm
)

py_library(
  NAME
    flax_overlay
  SRCS
    flax_overlay.py
  DEPS
    .dataclass_overlay
    pytype.libvm
)

py_library(
  NAME
    future_overlay
  SRCS
    future_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    six_overlay
  SRCS
    six_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    subprocess_overlay
  SRCS
    subprocess_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    sys_overlay
  SRCS
    sys_overlay.py
  DEPS
    pytype.libvm
)

py_library(
  NAME
    typing_extensions_overlay
  SRCS
    typing_extensions_overlay.py
  DEPS
    .typing_overlay
    pytype.libvm
)

py_library(
  NAME
    typing_overlay
  SRCS
    typing_overlay.py
  DEPS
    .classgen
    .collections_overlay
    pytype.libvm
)

py_test(
  NAME
    collections_overlay_test
  SRCS
    collections_overlay_test.py
  DEPS
    .collections_overlay
    pytype.pytd.pytd_defs
    pytype.pytd.pytd_for_parser
    pytype.pytd.pytd_utils
    pytype.tests.test_base
)

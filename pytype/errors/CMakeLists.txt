add_package()

py_library(
  NAME
    errors
  DEPS
    ._errors
    .error_printer
)

py_library(
  NAME
    _errors
  SRCS
    errors.py
  DEPS
    .error_printer
    pytype._utils
    pytype.debug
    pytype.pretty_printer
    pytype.abstract.abstract
    pytype.overlays.overlays
    pytype.pytd.pytd
)

py_library(
  NAME
    error_printer
  SRCS
    error_printer.py
  DEPS
    pytype.matcher
    pytype.pretty_printer
    pytype.abstract.abstract
    pytype.overlays.overlays
    pytype.pytd.pytd
    pytype.typegraph.cfg
)

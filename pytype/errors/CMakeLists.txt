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
    .error_types
    pytype._utils
    pytype.debug
    pytype.pretty_printer_base
    pytype.pytd.pytd
    pytype.types.types
)

py_library(
  NAME
    error_printer
  SRCS
    error_printer.py
  DEPS
    pytype.matcher
    pytype.pretty_printer_base
    pytype.pytd.pytd
    pytype.typegraph.cfg
    pytype.types.types
)

py_library(
  NAME
    error_types
  SRCS
    error_types.py
  DEPS
    pytype.types.types
)

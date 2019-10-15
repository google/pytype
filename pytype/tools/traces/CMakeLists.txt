add_package()

toplevel_py_binary(
  NAME
    run
  SRCS
    run.py
  MAIN
    run.py
  DEPS
    .traces
    pytype.config
)

py_library(
  NAME
    traces
  SRCS
    traces.py
  DEPS
    .source
    .visitor
    pytype.config
    pytype.errors
    pytype.libvm
    pytype.pytd_defs
    pytype.pytd_for_parser
)

py_test(
  NAME
    traces_test
  SRCS
    traces_test.py
  DEPS
    .traces
    pytype.config
    pytype.pytd_defs
    pytype.utils
)

py_library(
  NAME
    source
  SRCS
    source.py
)

py_test(
  NAME
    source_test
  SRCS
    source_test.py
  DEPS
    .source
)

py_library(
  NAME
    visitor
  SRCS
    visitor.py
)

py_test(
  NAME
    visitor_test
  SRCS
    visitor_test.py
  DEPS
    .visitor
)

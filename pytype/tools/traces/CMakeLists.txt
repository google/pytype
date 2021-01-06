add_package()

toplevel_py_binary(
  NAME
    run
  SRCS
    run.py
  MAIN
    run.py
  DEPS
    ._traces
    pytype.libvm
)

py_library(
  NAME
    traces
  DEPS
    ._traces
    .source
)

py_library(
  NAME
    _traces
  SRCS
    traces.py
  DEPS
    .source
    pytype.libvm
    pytype.ast.ast
    pytype.pytd.pytd
)

py_test(
  NAME
    traces_test
  SRCS
    traces_test.py
  DEPS
    ._traces
    pytype.libvm
    pytype.utils
    pytype.pytd.pytd
    pytype.tests.test_base
)

py_library(
  NAME
    source
  SRCS
    source.py
  DEPS
    pytype.utils
)

py_test(
  NAME
    source_test
  SRCS
    source_test.py
  DEPS
    .source
)

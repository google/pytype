add_package()

py_library(
  NAME
    codegen
  DEPS
    .function
    .namedtuple
    .pytdgen
)

py_library(
  NAME
    function
  SRCS
    function.py
  DEPS
    pytype.pytd.pytd_for_codegen
    pytype.pytd.parse.parse
)

py_library(
  NAME
    namedtuple
  SRCS
    namedtuple.py
  DEPS
    .function
    .pytdgen
    pytype.pytd.pytd_for_codegen
)

py_library(
  NAME
    pytdgen
  SRCS
    pytdgen.py
  DEPS
    pytype.pytd.pytd_for_codegen
    pytype.pytd.parse.parse
)

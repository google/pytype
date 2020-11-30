add_package()

toplevel_py_binary(
  NAME
    annotate
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    .annotate_ast
    pytype.ast.visitor
    pytype.tools
)

py_library(
  NAME
    annotate_ast
  SRCS
    annotate_ast.py
  DEPS
    pytype.io
    pytype.pytd.pytd_for_parser
    pytype.tools.traces.traces
)

py_test(
  NAME
    annotate_ast_test
  SRCS
    annotate_ast_test.py
  DEPS
    .annotate_ast
    pytype.config
    pytype.tests.test_base
)

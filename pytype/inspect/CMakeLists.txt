add_package()

py_library(
  NAME
    inspect
  DEPS
    .graph
    .init
)

py_library(
  NAME
    graph
  SRCS
    graph.py
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_test(
  NAME
    graph_test
  SRCS
    graph_test.py
  DEPS
    .graph
    pytype.typegraph.cfg
)

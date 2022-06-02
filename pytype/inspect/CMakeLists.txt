add_package()

py_library(
  NAME
    graph
  SRCS
    graph.py
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

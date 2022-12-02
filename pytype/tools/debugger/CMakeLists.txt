add_package()

toplevel_py_binary(
  NAME
    debug_pytype
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    .visualizer
    pytype.libvm
    pytype.utils
    pytype.inspect.inspect
    pytype.tools.tools
)

py_library(
  NAME
    visualizer
  SRCS
    __init__.py
    visualizer.py
  DEPS
    pytype.typegraph.cfg
    pytype.typegraph.typegraph_serializer
)

add_package()

toplevel_py_binary(
  NAME
    debug_pytype
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    pytype.libvm
    pytype.utils
    pytype.inspect.inspect
    pytype.tools.tools
)

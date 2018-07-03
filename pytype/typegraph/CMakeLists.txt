add_package()

py_test(
  NAME
    cfg_test
  SRCS
    cfg_test.py
  DEPS
    .cfg
)

py_test(
  NAME
    cfg_utils_test
  SRCS
    cfg_utils_test.py
  DEPS
    .cfg
    pytype.cfg_utils
)

py_extension(
  NAME
    cfg
  SRCS
    cfg.cc
    map_util.h
    memory_util.h
    reachable.cc
    reachable.h
    solver.cc
    solver.h
    typegraph.cc
    typegraph.h
)

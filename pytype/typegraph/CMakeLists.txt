add_package()

cc_library(
  NAME
    cfg_logging
  SRCS
    cfg_logging.cc
    pylogging.cc
  HDRS
    cfg_logging.h
    pylogging.h
)

cc_library(
  NAME
    reachable
  SRCS
    reachable.cc
  HDRS
    reachable.h
)

cc_test(
  NAME
    reachable_test
  SRCS
    reachable_test.cc
  DEPS
    .reachable
)

cc_library(
  NAME
    metrics
  HDRS
    metrics.h
)

cc_library(
  NAME
    typegraph
  SRCS
    solver.cc
    typegraph.cc
  HDRS
    solver.h
    typegraph.h
  DEPS
    .cfg_logging
    .reachable
)

cc_test(
  NAME
    typegraph_test
  SRCS
    typegraph_test.cc
  DEPS
    .typegraph
)

cc_test(
  NAME
    solver_test
  SRCS
    solver_test.cc
  DEPS
    .typegraph
)

cc_test(
  NAME
    map_util_test
  SRCS
    map_util_test.cc
)

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

pybind11_add_module(
  # NAME -- this must be the fully qualified name.
    pytype.typegraph.cfg
  # Library type -- py_extensions are always SHARED.
    SHARED
  # SRCS
    cfg.cc
    cfg_logging.cc
    cfg_logging.h
    map_util.h
    memory_util.h
    metrics.h
    pylogging.cc
    pylogging.h
    reachable.cc
    reachable.h
    solver.cc
    solver.h
    typegraph.cc
    typegraph.h
)

# pybind11_add_module changes the name of the output library, which makes
# pytype unable to discover it.
set_target_properties(
    pytype.typegraph.cfg
    PROPERTIES
    PREFIX ""
    SUFFIX ".so"
    OUTPUT_NAME cfg
)

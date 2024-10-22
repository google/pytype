add_package()

# BEGIN keep
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
if (WIN32)
  set_target_properties(
    pytype.typegraph.cfg
    PROPERTIES
    PREFIX ""
    OUTPUT_NAME cfg
  )
else()
  set_target_properties(
    pytype.typegraph.cfg
    PROPERTIES
    PREFIX ""
    SUFFIX ".so"
    OUTPUT_NAME cfg
  )
endif()
# END keep

py_library(
  NAME
    cfg_utils
  SRCS
    cfg_utils.py
  DEPS
    .cfg
)

py_library(
  NAME
    typegraph_serializer
  SRCS
    typegraph_serializer.py
  DEPS
    .cfg
    pytype.pytd.pytd
)

cc_library(
  NAME
    cfg_logging
  SRCS
    cfg_logging.cc
  HDRS
    cfg_logging.h
  DEPS
    .pylogging
)

cc_library(
  NAME
    pylogging
  SRCS
    pylogging.cc
  HDRS
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

cc_library(
  NAME
    typegraph
  SRCS
    solver.cc
    typegraph.cc
    map_util.h
    metrics.h
  HDRS
    solver.h
    typegraph.h
  DEPS
    .cfg_logging
    .reachable
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
    .cfg_utils
)

cc_test(
  NAME
    map_util_test
  SRCS
    map_util_test.cc
    map_util.h
)

cc_test(
  NAME
    reachable_test
  SRCS
    reachable_test.cc
  DEPS
    .reachable
)

cc_test(
  NAME
    solver_test
  SRCS
    solver_test.cc
    test_util.h
  DEPS
    .typegraph
)

cc_test(
  NAME
    typegraph_test
  SRCS
    typegraph_test.cc
    test_util.h
  DEPS
    .typegraph
)

py_test(
  NAME
    typegraph_serializer_test
  SRCS
    typegraph_serializer_test.py
  DEPS
    .typegraph_serializer
    pytype.tests.test_base
    pytype.tests.test_utils
)

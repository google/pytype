add_package()

py_library(
  NAME
    test_base
  SRCS
    test_base.py
    test_utils.py
  DEPS
    pytype.analyze
    pytype.config
    pytype.libvm
)

py_test(
  NAME
    test_base_test
  SRCS
    test_base_test.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_basic
  SRCS
    test_basic.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_anystr
  SRCS
    test_anystr.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_match
  SRCS
    test_match.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_decorators
  SRCS
    test_decorators.py
  DEPS
    .test_base
)

py_test(
    NAME
      test_dict
    SRCS
      test_dict.py
    DEPS
      .test_base
)

py_test(
  NAME
    test_exceptions
  SRCS
    test_exceptions.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_functions
  SRCS
    test_functions.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_generators
  SRCS
    test_generators.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_quick
  SRCS
    test_quick.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_slice
  SRCS
    test_slice.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_slots
  SRCS
    test_slots.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_splits
  SRCS
    test_splits.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_super
  SRCS
    test_super.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_tuple
  SRCS
    test_tuple.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_type_comments
  SRCS
    test_type_comments.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_unions
  SRCS
    test_unions.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_with
  SRCS
    test_with.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_attributes
  SRCS
    test_attributes.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_builtins1
  SRCS
    test_builtins1.py
  DEPS
    .test_base
    pytype.overlays.collections_overlay
)

py_test(
  NAME
    test_builtins2
  SRCS
    test_builtins2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_builtins3
  SRCS
    test_builtins3.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_special_builtins
  SRCS
    test_special_builtins.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_stdlib
  SRCS
    test_stdlib.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_classes
  SRCS
    test_classes.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_cmp
  SRCS
    test_cmp.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_containers
  SRCS
    test_containers.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_flow
  SRCS
    test_flow.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_methods
  SRCS
    test_methods.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_closures
  SRCS
    test_closures.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_disables
  SRCS
    test_disables.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_errors
  SRCS
    test_errors.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_tracebacks
  SRCS
    test_tracebacks.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_pickle
  SRCS
    test_pickle.py
  DEPS
     .test_base
)

py_test(
  NAME
    test_reingest
  SRCS
    test_reingest.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_list
  SRCS
    test_list.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_logic
  SRCS
    test_logic.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_typevar
  SRCS
    test_typevar.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_options
  SRCS
    test_options.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_calls
  SRCS
    test_calls.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_import
  SRCS
    test_import.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_pyi
  SRCS
    test_pyi.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_generic
  SRCS
    test_generic.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_inheritance
  SRCS
    test_inheritance.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_operators
  SRCS
    test_operators.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_operators2
  SRCS
    test_operators2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_inplace
  SRCS
    test_inplace.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_recovery
  SRCS
    test_recovery.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_solver
  SRCS
    test_solver.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_typing
  SRCS
    test_typing.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_typing_methods
  SRCS
    test_typing_methods.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_typing_namedtuple
  SRCS
    test_typing_namedtuple.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_protocols
  SRCS
    test_protocols.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_protocol_inference
  SRCS
    test_protocol_inference.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_namedtuple
  SRCS
    test_namedtuple.py
  DEPS
    .test_base
    pytype.overlays.collections_overlay
)

py_test(
  NAME
    test_abc
  SRCS
    test_abc.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_attr
  SRCS
    test_attr.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_six_overlay
  SRCS
    test_six_overlay.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_future_overlay
  SRCS
    test_future_overlay.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_compile_to_pyc
  SRCS
    test_compile_to_pyc.py
  DEPS
    .test_base
)

add_subdirectory(py2)
add_subdirectory(py3)

add_package()

py_test(
  NAME
    test_abc
  SRCS
    test_abc.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_annotations
  SRCS
    test_annotations.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_anystr
  SRCS
    test_anystr.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_attr
  SRCS
    test_attr.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_checker
  SRCS
    test_checker.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_protocols
  SRCS
    test_protocols.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_tracebacks
  SRCS
    test_tracebacks.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_calls
  SRCS
    test_calls.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_cmp
  SRCS
    test_cmp.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_decorators
  SRCS
    test_decorators.py
  DEPS
    pytype.utils
    pytype.pytd.pytd_utils
    pytype.tests.test_base
)

py_test(
  NAME
    test_errors
  SRCS
    test_errors.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_exceptions
  SRCS
    test_exceptions.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_flow
  SRCS
    test_flow.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_functions
  SRCS
    test_functions.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_inplace
  SRCS
    test_inplace.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_list
  SRCS
    test_list.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_match
  SRCS
    test_match.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_namedtuple
  SRCS
    test_namedtuple.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_typing
  SRCS
    test_typing.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_typing_methods
  SRCS
    test_typing_methods.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_typing_namedtuple
  SRCS
    test_typing_namedtuple.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_classes
  SRCS
    test_classes.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_basic
  SRCS
    test_basic.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_attributes
  SRCS
    test_attributes.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_builtins
  SRCS
    test_builtins.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_import
  SRCS
    test_import.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_pyi
  SRCS
    test_pyi.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_methods
  SRCS
    test_methods.py
  DEPS
    pytype.utils
    pytype.tests.test_base
)

py_test(
  NAME
    test_generators
  SRCS
    test_generators.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_six_overlay
  SRCS
    test_six_overlay.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_recovery
  SRCS
    test_recovery.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_reingest
  SRCS
    test_reingest.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_slice
  SRCS
    test_slice.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_special_builtins
  SRCS
    test_special_builtins.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_splits
  SRCS
    test_splits.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_typevar
  SRCS
    test_typevar.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_operators
  SRCS
    test_operators.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_slots
  SRCS
    test_slots.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_tuple
  SRCS
    test_tuple.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_type_comments
  SRCS
    test_type_comments.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_stdlib
  SRCS
    test_stdlib.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_super
  SRCS
    test_super.py
  DEPS
    pytype.utils
    pytype.tests.test_base
)

py_test(
  NAME
    test_dict
  SRCS
    test_dict.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_pickle
  SRCS
    test_pickle.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_quick
  SRCS
    test_quick.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_generic
  SRCS
    test_generic.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_variable_annotations
  SRCS
    test_variable_annotations.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_coroutine
  SRCS
    test_coroutine.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_async_generators
  SRCS
    test_async_generators.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_overload
  SRCS
    test_overload.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_dataclasses
  SRCS
    test_dataclasses.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_flax_overlay
  SRCS
    test_flax_overlay.py
  DEPS
    pytype.tests.test_base
)

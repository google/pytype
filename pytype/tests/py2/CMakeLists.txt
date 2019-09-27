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
    test_anystr
  SRCS
    test_anystr.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_protocol_inference
  SRCS
    test_protocol_inference.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_containers
  SRCS
    test_containers.py
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
    test_functions
  SRCS
    test_functions.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_decorators
  SRCS
    test_decorators.py
  DEPS
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
    test_six_overlay
  SRCS
    test_six_overlay.py
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
    test_super
  SRCS
    test_super.py
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
    test_stdlib
  SRCS
    test_stdlib.py
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

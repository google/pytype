add_package()

py_library(
  NAME
    test_base
  DEPS
    ._test_base
    .test_utils
)

py_library(
  NAME
    _test_base
  SRCS
    test_base.py
  DEPS
    .test_utils
    pytype.libvm
    pytype.pyi.parser
    pytype.pytd.pytd
)

py_library(
  NAME
    test_utils
  SRCS
    test_utils.py
  DEPS
    pytype.libvm
    pytype.pyc.pyc
)

py_test(
  NAME
    test_base_test
  SRCS
    test_base_test.py
  DEPS
    ._test_base
    .test_utils
    pytype.utils
)

py_test(
  NAME
    test_basic1
  SRCS
    test_basic1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_basic2
  SRCS
    test_basic2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_anystr1
  SRCS
    test_anystr1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_anystr2
  SRCS
    test_anystr2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_match1
  SRCS
    test_match1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_match2
  SRCS
    test_match2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_decorators1
  SRCS
    test_decorators1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_decorators2
  SRCS
    test_decorators2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_dict1
  SRCS
    test_dict1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_dict2
  SRCS
    test_dict2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_exceptions1
  SRCS
    test_exceptions1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_exceptions2
  SRCS
    test_exceptions2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_functions1
  SRCS
    test_functions1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_functions2
  SRCS
    test_functions2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_generators1
  SRCS
    test_generators1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_generators2
  SRCS
    test_generators2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_quick1
  SRCS
    test_quick1.py
  DEPS
    .test_base
    pytype.pytd.pytd
)

py_test(
  NAME
    test_quick2
  SRCS
    test_quick2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_slice1
  SRCS
    test_slice1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_slice2
  SRCS
    test_slice2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_slots1
  SRCS
    test_slots1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_slots2
  SRCS
    test_slots2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_splits1
  SRCS
    test_splits1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_splits2
  SRCS
    test_splits2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_super1
  SRCS
    test_super1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_super2
  SRCS
    test_super2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_tuple1
  SRCS
    test_tuple1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_tuple2
  SRCS
    test_tuple2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_type_comments1
  SRCS
    test_type_comments1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_type_comments2
  SRCS
    test_type_comments2.py
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
    test_attributes1
  SRCS
    test_attributes1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_attributes2
  SRCS
    test_attributes2.py
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
    pytype.overlays.overlays
    pytype.pytd.pytd
)

py_test(
  NAME
    test_builtins2
  SRCS
    test_builtins2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_builtins3
  SRCS
    test_builtins3.py
  DEPS
    .test_base
    pytype.libvm
    pytype.utils
)

py_test(
  NAME
    test_builtins4
  SRCS
    test_builtins4.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_special_builtins1
  SRCS
    test_special_builtins1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_special_builtins2
  SRCS
    test_special_builtins2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_stdlib1
  SRCS
    test_stdlib1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_stdlib2
  SRCS
    test_stdlib2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_classes1
  SRCS
    test_classes1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_classes2
  SRCS
    test_classes2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_cmp1
  SRCS
    test_cmp1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_cmp2
  SRCS
    test_cmp2.py
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
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_flow1
  SRCS
    test_flow1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_flow2
  SRCS
    test_flow2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_methods1
  SRCS
    test_methods1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_methods2
  SRCS
    test_methods2.py
  DEPS
    .test_base
    pytype.utils
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
    test_errors1
  SRCS
    test_errors1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_errors2
  SRCS
    test_errors2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_tracebacks1
  SRCS
    test_tracebacks1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_tracebacks2
  SRCS
    test_tracebacks2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_pickle1
  SRCS
    test_pickle1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pyi.parser
    pytype.pytd.pytd
)

py_test(
  NAME
    test_pickle2
  SRCS
    test_pickle2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_reingest1
  SRCS
    test_reingest1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_reingest2
  SRCS
    test_reingest2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_list1
  SRCS
    test_list1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_list2
  SRCS
    test_list2.py
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
    test_typevar1
  SRCS
    test_typevar1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_typevar2
  SRCS
    test_typevar2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
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
    test_calls1
  SRCS
    test_calls1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_calls2
  SRCS
    test_calls2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_import1
  SRCS
    test_import1.py
  DEPS
    .test_base
    pytype.libvm
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_import2
  SRCS
    test_import2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_pyi1
  SRCS
    test_pyi1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_pyi2
  SRCS
    test_pyi2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_generic1
  SRCS
    test_generic1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_generic2
  SRCS
    test_generic2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_inheritance
  SRCS
    test_inheritance.py
  DEPS
    .test_base
    pytype.pytd.pytd
)

py_test(
  NAME
    test_operators1
  SRCS
    test_operators1.py
  DEPS
    .test_base
    .test_utils
    pytype.utils
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
    test_operators3
  SRCS
    test_operators3.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_inplace1
  SRCS
    test_inplace1.py
  DEPS
    .test_base
    .test_utils
)

py_test(
  NAME
    test_inplace2
  SRCS
    test_inplace2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_recovery1
  SRCS
    test_recovery1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_recovery2
  SRCS
    test_recovery2.py
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
    pytype.utils
)

py_test(
  NAME
    test_typing1
  SRCS
    test_typing1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_typing2
  SRCS
    test_typing2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_typing_methods1
  SRCS
    test_typing_methods1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_typing_methods2
  SRCS
    test_typing_methods2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_typing_namedtuple1
  SRCS
    test_typing_namedtuple1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_typing_namedtuple2
  SRCS
    test_typing_namedtuple2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_protocols1
  SRCS
    test_protocols1.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_protocols2
  SRCS
    test_protocols2.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_protocol_inference
  SRCS
    test_protocol_inference.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_namedtuple1
  SRCS
    test_namedtuple1.py
  DEPS
    .test_base
    pytype.utils
    pytype.overlays.overlays
    pytype.pytd.pytd
)

py_test(
  NAME
    test_namedtuple2
  SRCS
    test_namedtuple2.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_abc1
  SRCS
    test_abc1.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_abc2
  SRCS
    test_abc2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_attr1
  SRCS
    test_attr1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_attr2
  SRCS
    test_attr2.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_six_overlay1
  SRCS
    test_six_overlay1.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_six_overlay2
  SRCS
    test_six_overlay2.py
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
    pytype.utils
)

py_test(
  NAME
    test_compile_to_pyc
  SRCS
    test_compile_to_pyc.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_typing_annotated
  SRCS
    test_typing_annotated.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_annotations
  SRCS
    test_annotations.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_checker
  SRCS
    test_checker.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_unpack
  SRCS
    test_unpack.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_variable_annotations
  SRCS
    test_variable_annotations.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_coroutine
  SRCS
    test_coroutine.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_async_generators
  SRCS
    test_async_generators.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_overload
  SRCS
    test_overload.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_dataclasses
  SRCS
    test_dataclasses.py
  DEPS
    .test_base
    pytype.utils
)

py_test(
  NAME
    test_chex_overlay
  SRCS
    test_chex_overlay.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_flax_overlay
  SRCS
    test_flax_overlay.py
  DEPS
    .test_base
    pytype.utils
    pytype.pytd.pytd
)

py_test(
  NAME
    test_enums
  SRCS
    test_enums.py
  DEPS
    .test_base
    pytype.utils
)

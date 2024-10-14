"""The abstract values used by vm.py.

This file contains BaseValue and its subclasses. Mixins such as Class
are in mixin.py, and other abstract logic is in abstract_utils.py.
"""

import logging

from pytype.abstract import _base
from pytype.abstract import _classes
from pytype.abstract import _function_base
from pytype.abstract import _instance_base
from pytype.abstract import _instances
from pytype.abstract import _interpreter_function
from pytype.abstract import _pytd_function
from pytype.abstract import _singletons
from pytype.abstract import _typing
from pytype.abstract import class_mixin
from pytype.abstract import mixin

log: logging.Logger = logging.getLogger(__name__)

# For simplicity, we pretend all abstract values are defined in abstract.py.
BaseValue: type[_base.BaseValue] = _base.BaseValue

# These are technically mixins, but we use them a lot in isinstance() checks.
Class: type[class_mixin.Class] = class_mixin.Class
PythonConstant: type[mixin.PythonConstant] = mixin.PythonConstant

BuildClass: type[_classes.BuildClass] = _classes.BuildClass
InterpreterClass: type[_classes.InterpreterClass] = _classes.InterpreterClass
PyTDClass: type[_classes.PyTDClass] = _classes.PyTDClass
FunctionPyTDClass: type[_classes.FunctionPyTDClass] = _classes.FunctionPyTDClass
ParameterizedClass: type[_classes.ParameterizedClass] = (
    _classes.ParameterizedClass
)
CallableClass: type[_classes.CallableClass] = _classes.CallableClass
LiteralClass: type[_classes.LiteralClass] = _classes.LiteralClass
TupleClass: type[_classes.TupleClass] = _classes.TupleClass

Function: type[_function_base.Function] = _function_base.Function
NativeFunction: type[_function_base.NativeFunction] = (
    _function_base.NativeFunction
)
BoundFunction: type[_function_base.BoundFunction] = _function_base.BoundFunction
BoundInterpreterFunction: type[_function_base.BoundInterpreterFunction] = (
    _function_base.BoundInterpreterFunction
)
BoundPyTDFunction: type[_function_base.BoundPyTDFunction] = (
    _function_base.BoundPyTDFunction
)
ClassMethod: type[_function_base.ClassMethod] = _function_base.ClassMethod
StaticMethod: type[_function_base.StaticMethod] = _function_base.StaticMethod
Property: type[_function_base.Property] = _function_base.Property
SignedFunction: type[_function_base.SignedFunction] = (
    _function_base.SignedFunction
)
SimpleFunction: type[_function_base.SimpleFunction] = (
    _function_base.SimpleFunction
)

SimpleValue: type[_instance_base.SimpleValue] = _instance_base.SimpleValue
Instance: type[_instance_base.Instance] = _instance_base.Instance

LazyConcreteDict: type[_instances.LazyConcreteDict] = (
    _instances.LazyConcreteDict
)
ConcreteValue: type[_instances.ConcreteValue] = _instances.ConcreteValue
Module: type[_instances.Module] = _instances.Module
Coroutine: type[_instances.Coroutine] = _instances.Coroutine
Iterator: type[_instances.Iterator] = _instances.Iterator
BaseGenerator: type[_instances.BaseGenerator] = _instances.BaseGenerator
AsyncGenerator: type[_instances.AsyncGenerator] = _instances.AsyncGenerator
Generator: type[_instances.Generator] = _instances.Generator
Tuple: type[_instances.Tuple] = _instances.Tuple
List: type[_instances.List] = _instances.List
Dict: type[_instances.Dict] = _instances.Dict
AnnotationsDict: type[_instances.AnnotationsDict] = _instances.AnnotationsDict
Splat: type[_instances.Splat] = _instances.Splat
SequenceLength: type[_instances.SequenceLength] = _instances.SequenceLength

InterpreterFunction: type[_interpreter_function.InterpreterFunction] = (
    _interpreter_function.InterpreterFunction
)

PyTDFunction: type[_pytd_function.PyTDFunction] = _pytd_function.PyTDFunction
PyTDSignature: type[_pytd_function.PyTDSignature] = _pytd_function.PyTDSignature
SignatureMutationError: type[_pytd_function.SignatureMutationError] = (
    _pytd_function.SignatureMutationError
)

Unknown: type[_singletons.Unknown] = _singletons.Unknown
Singleton: type[_singletons.Singleton] = _singletons.Singleton
Empty: type[_singletons.Empty] = _singletons.Empty
Deleted: type[_singletons.Deleted] = _singletons.Deleted
Unsolvable: type[_singletons.Unsolvable] = _singletons.Unsolvable
Null: type[_singletons.Null] = _singletons.Null

AnnotationClass: type[_typing.AnnotationClass] = _typing.AnnotationClass
AnnotationContainer: type[_typing.AnnotationContainer] = (
    _typing.AnnotationContainer
)
ParamSpec: type[_typing.ParamSpec] = _typing.ParamSpec
ParamSpecArgs: type[_typing.ParamSpecArgs] = _typing.ParamSpecArgs
ParamSpecKwargs: type[_typing.ParamSpecKwargs] = _typing.ParamSpecKwargs
ParamSpecInstance: type[_typing.ParamSpecInstance] = _typing.ParamSpecInstance
Concatenate: type[_typing.Concatenate] = _typing.Concatenate
TypeParameter: type[_typing.TypeParameter] = _typing.TypeParameter
TypeParameterInstance: type[_typing.TypeParameterInstance] = (
    _typing.TypeParameterInstance
)
Union: type[_typing.Union] = _typing.Union
LateAnnotation: type[_typing.LateAnnotation] = _typing.LateAnnotation
FinalAnnotation: type[_typing.FinalAnnotation] = _typing.FinalAnnotation

AMBIGUOUS: tuple[type[Unknown], type[Unsolvable]] = (Unknown, Unsolvable)
AMBIGUOUS_OR_EMPTY: tuple[type[Unknown], type[Unsolvable], type[Empty]] = (
    AMBIGUOUS + (Empty,)
)
FUNCTION_TYPES: tuple[type[BoundFunction], type[Function]] = (
    BoundFunction,
    Function,
)
INTERPRETER_FUNCTION_TYPES: tuple[
    type[BoundInterpreterFunction], type[InterpreterFunction]
] = (BoundInterpreterFunction, InterpreterFunction)
PYTD_FUNCTION_TYPES: tuple[type[BoundPyTDFunction], type[PyTDFunction]] = (
    BoundPyTDFunction,
    PyTDFunction,
)
TYPE_VARIABLE_TYPES: tuple[type[TypeParameter], type[ParamSpec]] = (
    TypeParameter,
    ParamSpec,
)
TYPE_VARIABLE_INSTANCES: tuple[
    type[TypeParameterInstance], type[ParamSpecInstance]
] = (TypeParameterInstance, ParamSpecInstance)

AmbiguousOrEmptyType = Unknown | Unsolvable | Empty

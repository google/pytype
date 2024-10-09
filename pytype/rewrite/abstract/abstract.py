"""Abstract representations of Python values."""

from typing import TypeVar
from pytype.rewrite.abstract import base as _base
from pytype.rewrite.abstract import classes as _classes
from pytype.rewrite.abstract import containers as _containers
from pytype.rewrite.abstract import functions as _functions
from pytype.rewrite.abstract import internal as _internal
from pytype.rewrite.abstract import utils as _utils

_T = TypeVar('_T')

BaseValue: type[_base.BaseValue] = _base.BaseValue
ContextType: type[_base.ContextType] = _base.ContextType
PythonConstant: type[_base.PythonConstant] = _base.PythonConstant
Singleton: type[_base.Singleton] = _base.Singleton
Union: type[_base.Union] = _base.Union

SimpleClass: type[_classes.SimpleClass] = _classes.SimpleClass
BaseInstance: type[_classes.BaseInstance] = _classes.BaseInstance
FrozenInstance: type[_classes.FrozenInstance] = _classes.FrozenInstance
InterpreterClass: type[_classes.InterpreterClass] = _classes.InterpreterClass
Module: type[_classes.Module] = _classes.Module
MutableInstance: type[_classes.MutableInstance] = _classes.MutableInstance

Args: type[_functions.Args] = _functions.Args
BaseFunction: type[_functions.BaseFunction] = _functions.BaseFunction
BoundFunction: type[_functions.BoundFunction] = _functions.BoundFunction
FrameType: type[_functions.FrameType] = _functions.FrameType
InterpreterFunction: type[_functions.InterpreterFunction] = (
    _functions.InterpreterFunction
)
MappedArgs: type[_functions.MappedArgs] = _functions.MappedArgs
PytdFunction: type[_functions.PytdFunction] = _functions.PytdFunction
Signature: type[_functions.Signature] = _functions.Signature
SimpleFunction: type[_functions.SimpleFunction] = _functions.SimpleFunction
SimpleReturn: type[_functions.SimpleReturn] = _functions.SimpleReturn

Dict: type[_containers.Dict] = _containers.Dict
List: type[_containers.List] = _containers.List
Set: type[_containers.Set] = _containers.Set
Tuple: type[_containers.Tuple] = _containers.Tuple

FunctionArgDict: type[_internal.FunctionArgDict] = _internal.FunctionArgDict
FunctionArgTuple: type[_internal.FunctionArgTuple] = _internal.FunctionArgTuple
Splat: type[_internal.Splat] = _internal.Splat

get_atomic_constant = _utils.get_atomic_constant
join_values = _utils.join_values
is_any = _utils.is_any

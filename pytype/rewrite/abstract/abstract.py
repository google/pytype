"""Abstract representations of Python values."""

from pytype.rewrite.abstract import base as _base
from pytype.rewrite.abstract import classes as _classes
from pytype.rewrite.abstract import functions as _functions
from pytype.rewrite.abstract import utils as _utils

BaseValue = _base.BaseValue
PythonConstant = _base.PythonConstant
Union = _base.Union
ANY = _base.ANY
NULL = _base.NULL

BaseClass = _classes.BaseClass
BaseInstance = _classes.BaseInstance
FrozenInstance = _classes.FrozenInstance
InterpreterClass = _classes.InterpreterClass
MutableInstance = _classes.MutableInstance
BUILD_CLASS = _classes.BUILD_CLASS

Args = _functions.Args
BaseFunction = _functions.BaseFunction
BoundFunction = _functions.BoundFunction
FrameType = _functions.FrameType
InterpreterFunction = _functions.InterpreterFunction
MappedArgs = _functions.MappedArgs
Signature = _functions.Signature
SimpleFunction = _functions.SimpleFunction
SimpleReturn = _functions.SimpleReturn

get_atomic_constant = _utils.get_atomic_constant
join_values = _utils.join_values

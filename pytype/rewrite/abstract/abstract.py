"""Abstract representations of Python values."""

from pytype.rewrite.abstract import base as _base
from pytype.rewrite.abstract import classes as _classes
from pytype.rewrite.abstract import functions as _functions
from pytype.rewrite.abstract import utils as _utils

BaseValue = _base.BaseValue
PythonConstant = _base.PythonConstant
ANY = _base.ANY
NULL = _base.NULL

BaseClass = _classes.BaseClass
InterpreterClass = _classes.InterpreterClass
BUILD_CLASS = _classes.BUILD_CLASS

Args = _functions.Args
InterpreterFunction = _functions.InterpreterFunction

get_atomic_constant = _utils.get_atomic_constant

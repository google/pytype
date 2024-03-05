"""Abstract representations of Python values."""

from pytype.rewrite.abstract import base as _base
from pytype.rewrite.abstract import classes as _classes
from pytype.rewrite.abstract import functions as _functions
from pytype.rewrite.abstract import utils as _utils

BaseValue = _base.BaseValue
PythonConstant = _base.PythonConstant
NULL = _base.NULL

Class = _classes.Class
BUILD_CLASS = _classes.BUILD_CLASS

Function = _functions.Function

get_atomic_constant = _utils.get_atomic_constant

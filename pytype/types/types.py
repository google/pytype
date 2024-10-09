"""Basic datatypes for pytype.

This module contains generic base classes that are independent of the internal
representation of pytype objects. Classes here are intended to be largely opaque
types, with a few exposed methods and properties that code not tightly coupled
to the internal representation can use.

Some guiding princples:
- Types here should not depend on any other part of the pytype codebase, except
  possibly the pytd types.
- Representation-independent code like the test framework and error reporting
  module should use types from here wherever possible, rather than using
  concrete types from abstract/
- This module should be considered public, for code that uses pytype as a
  library.
"""

from typing import Any
from pytype.types import base
from pytype.types import classes
from pytype.types import functions
from pytype.types import instances


BaseValue: type[base.BaseValue] = base.BaseValue
Variable: Any = base.Variable

Attribute: type[classes.Attribute] = classes.Attribute
Class: type[classes.Class] = classes.Class

Arg: type[functions.Arg] = functions.Arg
Args: type[functions.Args] = functions.Args
Function: type[functions.Function] = functions.Function
Signature: type[functions.Signature] = functions.Signature

Module: type[instances.Module] = instances.Module
PythonConstant: type[instances.PythonConstant] = instances.PythonConstant

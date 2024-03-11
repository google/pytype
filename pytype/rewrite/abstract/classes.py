"""Abstract representations of classes."""

from typing import List, Mapping, Sequence

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions as functions_lib


class Class(base.BaseValue):
  """Base representation of a class."""

  def __init__(self, name: str, members: Mapping[str, base.BaseValue]):
    self.name = name
    self.members = members

    # These methods are attributes of individual classes so that they can be
    # easily customized. For example, unittest.TestCase would want to add
    # 'setUpClass' to its setup methods and 'setUp' to its initializers.

    # classmethods called on a class immediately after creation
    self.setup_methods: List[str] = []
    # classmethod called to create a class instance
    self.constructor = '__new__'
    # instance methods called on an instance immediately after creation
    self.initializers = ['__init__', '__post_init__']

  def __repr__(self):
    return f'Class({self.name})'


class InterpreterClass(Class):

  def __init__(
      self, name: str, members: Mapping[str, base.BaseValue],
      functions: Sequence[functions_lib.InterpreterFunction],
      classes: Sequence['InterpreterClass']):
    super().__init__(name, members)
    # Functions and classes defined in this class's body. Unlike 'members',
    # ignores the effects of post-definition transformations like decorators.
    self.functions = functions
    self.classes = classes


BUILD_CLASS = base.Singleton('BUILD_CLASS')

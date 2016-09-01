# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Preconditions for automatic argument checking."""

from ply import lex
from ply import yacc


class PreconditionError(ValueError):
  pass


class _Precondition(object):
  """Base class for preconditions."""

  def check(self, value):
    """Raise PreconditionError if value does not match condition."""
    raise NotImplementedError


class _ClassNamePrecondition(_Precondition):
  """Precondition that expects an instance of a specific class."""

  def __init__(self, class_name):
    super(_ClassNamePrecondition, self).__init__()
    self._class_name = class_name

  def check(self, value):
    actual = type(value).__name__
    if actual != self._class_name:
      raise PreconditionError(
          "actual=%s, expected=%s" % (actual, self._class_name))


class _IsInstancePrecondition(_Precondition):
  """Precondition that expects an instance of a class or subclass."""

  def __init__(self, cls):
    super(_IsInstancePrecondition, self).__init__()
    self._cls = cls

  def check(self, value):
    if not isinstance(value, self._cls):
      raise PreconditionError(
          "actual=%s, expected_superclass=%s" % (
              type(value).__name__, self._cls.__name__))


_REGISTERED_CLASSES = {}


def register(cls):
  """Register a class object for use in {X} syntax."""
  name = cls.__name__
  assert name not in _REGISTERED_CLASSES
  _REGISTERED_CLASSES[name] = _IsInstancePrecondition(cls)


class _TuplePrecondition(_Precondition):
  """Precondition that expects a tuple."""

  def __init__(self, element_condition):
    super(_TuplePrecondition, self).__init__()
    self._element_condition = element_condition

  def check(self, value):
    if not isinstance(value, tuple):
      raise PreconditionError(
          "actual=%s, expected=tuple" % type(value).__name__)
    for v in value:
      self._element_condition.check(v)


class _OrPrecondition(_Precondition):
  """Precondition that expects one of various choices to match."""

  def __init__(self, choices):
    super(_OrPrecondition, self).__init__()
    self._choices = choices

  def check(self, value):
    errors = []
    for c in self._choices:
      try:
        c.check(value)
        return
      except PreconditionError as e:
        errors.append(e)
    raise PreconditionError(" or ".join("(%s)" % e.message for e in errors))


class CallChecker(object):
  """Class that performs argument checks against a collection of conditions."""

  def __init__(self, condition_pairs):
    """Create a checker given a sequence of (name, precondition) pairs."""
    self._arg_sequence = tuple(condition_pairs)
    self._arg_map = dict(self._arg_sequence)

  def check(self, *args, **kwargs):
    """Raise PreconditionError if the actual call is invalid."""
    # This check is intended to be in addition to an actual call, so an
    # incorrect number of args or undefined kwargs should be caught elsewhere.
    for value, pair in zip(args, self._arg_sequence):
      name, condition = pair
      self._check_arg(condition, name, value)
    for name, value in kwargs.items():
      condition = self._arg_map.get(name)
      self._check_arg(condition, name, value)

  def _check_arg(self, condition, name, value):
    if condition:
      try:
        condition.check(value)
      except PreconditionError as e:
        raise PreconditionError("argument=%s: %s." % (name, e.message))


# Lexer
# pylint: disable=g-docstring-quotes, g-short-docstring-punctuation

tokens = ("NAME", "OR", "TUPLE", "NONE")
literals = ["[", "]", "{", "}"]

t_ignore = " \t\n"

_RESERVED = {
    "or": "OR",
    "tuple": "TUPLE",
    "None": "NONE",
    }


def t_NAME(t):  # pylint: disable=invalid-name
  r"[a-zA-Z_]\w*"
  t.type = _RESERVED.get(t.value, "NAME")
  return t


def t_error(t):
  raise ValueError("Invalid character: %s" % t.value[0])


_lexer = lex.lex()


# Parser

# It is better to have OR(a, b, c) than OR(OR(a, b), c), thus we use the
# following non-terminals:
#
# cond: A precondition.
# cond_list: A list of preconditions (the clauses of an OR)
# cond2: The cond productions other than an OR.


def p_cond(p):
  "cond : cond_list"
  cond_list = p[1]
  if len(cond_list) == 1:
    p[0] = cond_list[0]
  else:
    p[0] = _OrPrecondition(cond_list)


def p_cond_list_first(p):
  "cond_list : cond2"
  p[0] = [p[1]]


def p_cond_list_or(p):
  "cond_list : cond_list OR cond2"
  _, cond_list, _, cond2 = p
  p[0] = cond_list + [cond2]


def p_cond2_name(p):
  "cond2 : NAME"
  p[0] = _ClassNamePrecondition(p[1])


def p_cond2_none(p):
  "cond2 : NONE"
  p[0] = _ClassNamePrecondition("NoneType")


def p_cond2_tuple(p):
  "cond2 : TUPLE '[' cond ']'"
  p[0] = _TuplePrecondition(p[3])


def p_cond2_isinstance(p):
  "cond2 : '{' NAME '}'"
  name = p[2]
  cond = _REGISTERED_CLASSES.get(name)
  if cond is None:
    raise ValueError("Class '%s' is not registered for preconditions." % name)
  p[0] = cond


def p_error(p):
  del p
  raise ValueError("Syntax Error")


_parser = yacc.yacc(write_tables=False, debug=False)


# pylint: enable=g-docstring-quotes, g-short-docstring-punctuation


def parse(spec):
  """Return a _Precondition for the given string."""
  return _parser.parse(spec, lexer=_lexer)


def parse_arg(arg_spec):
  """Return (name, precondition) or (name, None) for given argument spec."""
  name, _, spec = arg_spec.partition(":")
  return name, parse(spec) if spec else None

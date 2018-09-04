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

import re

from pytype import utils


class PreconditionError(ValueError):
  pass


class _Precondition(object):
  """Base class for preconditions."""

  def check(self, value):
    """Raise PreconditionError if value does not match condition."""
    raise NotImplementedError

  def allowed_types(self):
    """Returns a set of types or typenames that are allowed."""
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

  def allowed_types(self):
    return {self._class_name}


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

  def allowed_types(self):
    return {self._cls}


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

  def allowed_types(self):
    return self._element_condition.allowed_types()


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
    raise PreconditionError(
        " or ".join("(%s)" % utils.message(e) for e in errors))

  def allowed_types(self):
    allowed = set()
    for c in self._choices:
      allowed |= c.allowed_types()
    return allowed


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
        raise PreconditionError("argument=%s: %s." % (name, utils.message(e)))

  def allowed_types(self):
    """Determines the types and typenames allowed by calls to the checker.

    Returns:
      A set of types and/or typenames (strings).  A typename matches
      only that one class while a type matches any subclass of the type.
    """
    allowed = set()
    for _, c in self._arg_sequence:
      allowed |= c.allowed_types()
    return allowed


# RE to match a single token.  Leading whitepace is ignored.
_TOKEN_RE = re.compile(
    r"\s*(?:(?P<literal>[\[\]{}])|(?P<word>[a-zA-Z_]\w*))")

# Token codes (aside from literal characters)
_TOKEN_NAME = 1
_TOKEN_TUPLE = 2
_TOKEN_OR = 3

_RESERVED = {
    "tuple": _TOKEN_TUPLE,
    "or": _TOKEN_OR,
}


class _Parser(object):
  """A parser for precondition specifications."""

  def __init__(self, spec):
    self._spec = spec.strip()  # Must strip trailing whitespace.
    self._pos = 0
    self._pending_token = None

  def parse(self):
    """Parse the spec and return a precondition."""
    cond = self._parse_or()
    self._expect(None)
    return cond

  def _peek_token(self):
    """Return the token code of the next token (do not consume token)."""
    if self._pending_token is None:
      self._pending_token = self._pop_token()
    return self._pending_token[0]

  def _pop_token(self):
    """Consume the next token and return (token_code, token_val)."""
    if self._pending_token is not None:
      result = self._pending_token
      self._pending_token = None
      return result

    if self._pos >= len(self._spec):
      return None, None
    m = _TOKEN_RE.match(self._spec, self._pos)
    if not m:
      raise ValueError("Syntax Error")
    self._pos = m.end()
    literal = m.group("literal")
    if literal:
      return literal, None
    word = m.group("word")
    t = _RESERVED.get(word)
    if t:
      return t, None
    else:
      return _TOKEN_NAME, word

  def _expect(self, expected_code):
    """Pop the next token, raise a ValueError if the code does not match."""
    t, val = self._pop_token()  # pylint: disable=unpacking-non-sequence
    if t != expected_code:
      raise ValueError("Syntax Error")
    return val

  def _parse_or(self):
    """Parse one or more conditions separated by "or"."""
    choices = [self._parse_one()]
    while self._peek_token() == _TOKEN_OR:
      self._pop_token()
      choices.append(self._parse_one())
    if len(choices) == 1:
      return choices[0]
    else:
      return _OrPrecondition(choices)

  def _parse_one(self):
    """Parse a single condition (not including "or")."""
    t, val = self._pop_token()  # pylint: disable=unpacking-non-sequence
    if t == _TOKEN_NAME:
      return _ClassNamePrecondition(val if val != "None" else "NoneType")
    elif t == "{":
      name = self._expect(_TOKEN_NAME)
      self._expect("}")
      cond = _REGISTERED_CLASSES.get(name)
      if cond is None:
        raise ValueError(
            "Class '%s' is not registered for preconditions." % name)
      return cond
    elif t == _TOKEN_TUPLE:
      self._expect("[")
      element = self._parse_or()
      self._expect("]")
      return _TuplePrecondition(element)
    raise ValueError("Syntax Error")


def parse(spec):
  """Return a _Precondition for the given string."""
  return _Parser(spec).parse()


def parse_arg(arg_spec):
  """Return (name, precondition) or (name, None) for given argument spec."""
  name, _, spec = arg_spec.partition(":")
  return name, parse(spec) if spec else None

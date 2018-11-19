# python3
"""Error classes for the pyi checker."""
from typing import TypeVar

from pytype.tools.pyi_checker import definitions


# Constant strings to make error message identation consistent.
_INDENT = "\n  "
_SOURCE = _INDENT + "Source:   "
_HINT = _INDENT + "Type hint: "


# Some errors apply to only Functions and only Classes.
_FUNC_OR_CLASS = TypeVar("_FUNC_OR_CLASS", definitions.Function,
                         definitions.Class)


class Error:
  """General error base class."""
  message: str
  lineno: int

  def __init__(self, message: str, lineno: int):
    self.message = message
    self.lineno = lineno


class MissingTypeHint(Error):
  """Error: A definition doesn't have a type hint."""

  def __init__(self, src_def: definitions.Definition) -> None:
    msg = "No type hint found for %s." % src_def.full_name
    super().__init__(msg, src_def.lineno)


class ExtraTypeHint(Error):
  """Error: A type hint doesn't have a matching source definition."""

  def __init__(self, type_hint: definitions.Definition) -> None:
    msg = "Type hint for %s has no corresponding source definition." % (
        type_hint.full_name)
    super().__init__(msg, type_hint.lineno)


class WrongTypeHint(Error):
  """Error: The type hint is the wrong kind of definition."""

  def __init__(self, src_def: definitions.Definition,
               type_hint: definitions.Definition) -> None:
    msg = "Type hint kind does not match source definition."
    msg += _SOURCE + src_def.full_name
    msg += _HINT + type_hint.full_name
    super().__init__(msg, type_hint.lineno)


class WrongDecorators(Error):
  """Error: The type hint has the wrong decorators."""

  def __init__(self, src_def: _FUNC_OR_CLASS,
               type_hint: _FUNC_OR_CLASS) -> None:
    # Maintain the order of decorators to make error messages clearer.
    missing_decs = [d for d in src_def.decorators
                    if d not in type_hint.decorators]
    extra_decs = [d for d in type_hint.decorators
                  if d not in src_def.decorators]
    msg = "Type hint for %s has incorrect decorators." % src_def.full_name
    if missing_decs:
      msg += _INDENT + "Missing in type hint: " + ", ".join(missing_decs)
    if extra_decs:
      msg += _INDENT + "Extras in type hint: " + ", ".join(extra_decs)
    super().__init__(msg, type_hint.lineno)


class WrongArgCount(Error):
  """Error: The number of positional arguments is wrong."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function) -> None:
    msg = "Type hint for %s has the wrong number of arguments." % (
        src_def.full_name)
    msg += _SOURCE + _just_args(src_def)
    msg += _HINT + _just_args(type_hint)
    super().__init__(msg, type_hint.lineno)


class WrongKwonlyCount(Error):
  """Error: The number of keyword-only arguments is wrong."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function) -> None:
    msg = "Type hint for %s has the wrong number of keyword-only arguments." % (
        src_def.full_name)
    msg += _SOURCE + _just_kwonlyargs(src_def)
    msg += _HINT + _just_kwonlyargs(type_hint)
    super().__init__(msg, type_hint.lineno)


class WrongArgName(Error):
  """Error: A positional argument is misnamed."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function, bad_name: str) -> None:
    msg = "%s has no argument named '%s'." % (
        src_def.full_name.capitalize(), bad_name)
    msg += _SOURCE + _just_args(src_def)
    msg += _HINT + _just_args(type_hint)
    super().__init__(msg, type_hint.lineno)


class WrongKwonlyName(Error):
  """Error: A keyword-only argument is misnamed."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function, bad_name: str) -> None:
    msg = "%s has no keyword-only argument named '%s'." % (
        src_def.full_name.capitalize(), bad_name)
    msg += _SOURCE + _just_kwonlyargs(src_def)
    msg += _HINT + _just_kwonlyargs(type_hint)
    super().__init__(msg, type_hint.lineno)


class WrongVararg(Error):
  """Error: The vararg is missing, extraneous, or misnamed."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function) -> None:
    src_vararg = src_def.vararg
    hint_vararg = type_hint.vararg
    if src_vararg and not hint_vararg:
      msg = "Type hint for %s is missing the vararg '*%s'." % (
          src_def.full_name, src_vararg.name)
      lineno = src_def.lineno
    elif not src_vararg and hint_vararg:
      msg = "Type hint for %s should not have vararg '*%s'." % (
          src_def.full_name, hint_vararg.name)
      lineno = hint_vararg.lineno
    else:
      msg = "Type hint for %s has wrong vararg name." % src_def.full_name
      msg += _SOURCE + _just_vararg(src_def)
      msg += _HINT + _just_vararg(type_hint)
      lineno = hint_vararg.lineno
    super().__init__(msg, lineno)


class WrongKwarg(Error):
  """Error: The keyword argument is missing, extraneous, or misnamed."""

  def __init__(self, src_def: definitions.Function,
               type_hint: definitions.Function) -> None:
    src_kwarg = src_def.kwarg
    hint_kwarg = type_hint.kwarg
    if src_kwarg and not hint_kwarg:
      msg = "Type hint for %s is missing keyword argument '**%s'." % (
          src_def.full_name, src_kwarg.name)
      lineno = src_kwarg.lineno
    elif not src_kwarg and hint_kwarg:
      msg = "Type hint for %s should not have keyword argument '**%s'." % (
          src_def.full_name, hint_kwarg.name)
      lineno = hint_kwarg.lineno
    else:
      msg = "Type hint for %s has wrong keyword argument name." % (
          src_def.full_name)
      msg += _SOURCE + _just_kwarg(src_def)
      msg += _HINT + _just_kwarg(type_hint)
      lineno = hint_kwarg.lineno
    super().__init__(msg, lineno)


# The following are helper functions for printing parts of a function's
# signature. This keeps error messages short and focused.
def _def(f: definitions.Function) -> str:
  return ("async def %s" if f.is_async else "def %s") % f.name


def _just_args(f: definitions.Function) -> str:
  """Creates a function signature with just the positional parameters.

  def f(a, b, *c, d, **e) will return "def f(a, b, ...)".

  Arguments:
    f: The function definition to print.

  Returns:
    The function signature with everything but the position parameters elided.
  """
  elems = [arg.name for arg in f.params]
  if f.vararg or f.kwonlyargs or f.kwarg:
    elems.append("...")
  return _def(f) + "(%s)" % ", ".join(elems)


def _just_vararg(f: definitions.Function) -> str:
  """Creates a function signature with just the vararg.

  def f(a, b, *c, d, **e) will return "def f(..., *c, ...)".
  def f(a, b) will return "def f(...)".

  Arguments:
    f: The function definition to print.

  Returns:
    The function signature with everything but the vararg elided.
  """
  if not f.vararg:
    return _just_noargs(f)
  elems = []
  if f.params:
    elems.append("...")
  elems.append("*%s" % f.vararg.name)
  if f.kwonlyargs or f.kwarg:
    elems.append("...")
  return _def(f) + "(%s)" % ", ".join(elems)


def _just_kwonlyargs(f: definitions.Function) -> str:
  """Creates a function signature with just the keyword-only arguments.

  def f(a, b, *c, d, **e) will return "def f(..., *c, d, ...)". The vararg is
  included to make it clear that keyword-only args are being printed.
  If there are no keyword-only arguments, will elide all arguments.

  Arguments:
    f: The function definition to print.

  Returns:
    The function signature with everything but the keyword-only args elided.
  """
  if not f.kwonlyargs:
    return _just_noargs(f)
  elems = []
  if f.params:
    elems.append("...")
  if f.vararg:
    elems.append("*%s" % f.vararg.name)
  else:
    elems.append("*")
  elems += [kw.name for kw in f.kwonlyargs]
  if f.kwarg:
    elems.append("...")
  return _def(f) + "(%s)" % ", ".join(elems)


def _just_kwarg(f: definitions.Function) -> str:
  """Creates a function signature with just the kwarg.

  def f(a, b, *c, d, **e) will return "def f(..., **e)".
  def f(a, b,) will return "def f(...)".

  Arguments:
    f: The function definition to print.

  Returns:
    The function signature with everything but the kwarg elided.
  """
  if not f.kwarg:
    return _just_noargs(f)
  elems = []
  if f.params or f.vararg or f.kwonlyargs:
    elems.append("...")
  elems.append("**%s" % f.kwarg.name)
  return _def(f) + "(%s)" % ", ".join(elems)


def _just_noargs(f: definitions.Function) -> str:
  """Creates a function signature with all args elided.

  If f has any arguments, will return "def f(...)".
  If it has no arguments, will return "def f()".

  Arguments:
    f: The function definition to print.

  Returns:
    The function signature with all arguments elided.
  """
  if f.params or f.vararg or f.kwonlyargs or f.kwarg:
    return _def(f) + "(...)"
  else:
    return _def(f) + "()"

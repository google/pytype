# python3
"""Useful functions for testing the pyi checker."""

import textwrap

from typing import List, Optional

from pytype.tools.pyi_checker import definitions
from typed_ast import ast3


def parse_stmt(source):
  """Helper for parsing single statements."""
  return ast3.parse(textwrap.dedent(source)).body[0]


def parse_expr(source: str):
  """Helper for parsing single expressions."""
  return ast3.parse(textwrap.dedent(source), mode="eval").body


def var_from_source(source: str) -> definitions.Variable:
  return definitions.Variable.from_node(parse_expr(source))


def func_from_source(source: str) -> definitions.Function:
  return definitions.Function.from_node(parse_stmt(source))


def class_from_source(source: str) -> definitions.Class:
  node = parse_stmt(source)
  return definitions.Class.from_node(node, [], [], [])


def make_func(name: str,
              lineno: int = 1,
              col_offset: int = 0,
              params: List[definitions.Argument] = None,
              vararg: Optional[definitions.Argument] = None,
              kwonlyargs: List[definitions.Argument] = None,
              kwarg: Optional[definitions.Argument] = None,
              decorators: List[str] = None,
              is_async: bool = False) -> definitions.Function:
  """Creates a definition.Function with default values."""
  params = params or []
  kwonlyargs = kwonlyargs or []
  decorators = decorators or []
  return definitions.Function(name=name, source="",
                              lineno=lineno, col_offset=col_offset,
                              params=params, vararg=vararg,
                              kwonlyargs=kwonlyargs, kwarg=kwarg,
                              decorators=decorators, is_async=is_async)


def make_arg(name: str,
             lineno: int = 1,
             col_offset: int = 0,
             has_default: bool = False) -> definitions.Argument:
  return definitions.Argument(name=name, source="",
                              lineno=lineno, col_offset=col_offset,
                              has_default=has_default)

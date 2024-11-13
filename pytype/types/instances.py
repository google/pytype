"""Basic datatypes for instances."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from pytype.types import base

if TYPE_CHECKING:
  from pytype.abstract import _base  # pylint: disable=g-import-not-at-top, g-bad-import-order


class Module:
  name: str


class PythonConstant:
  pyval: "_base.BaseValue | None"
  is_concrete: bool

  def str_of_constant(self, printer: Callable[[base.BaseValue], str]) -> str:
    raise NotImplementedError()

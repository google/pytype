"""Abstract representations of classes."""

from typing import Mapping

from pytype.rewrite.abstract import base


class Class(base.BaseValue):

  def __init__(self, name: str, members: Mapping[str, base.BaseValue]):
    self.name = name
    self.members = members

  def __repr__(self):
    return f'Class({self.name})'


BUILD_CLASS = base.Singleton('BUILD_CLASS')

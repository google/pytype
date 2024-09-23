"""TypeVar test."""
from typing import TypeVar

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class UserDict:

  def __init__(self, initialdata: dict[_KT, _VT] = None):
    pass

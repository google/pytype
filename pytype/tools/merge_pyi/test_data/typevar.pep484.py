# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
"""TypeVar test."""
from typing import Dict, TypeVar

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class UserDict(object):
    def __init__(self, initialdata: Dict[_KT, _VT] = None):
        pass

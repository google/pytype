from typing import Any
# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
def f1(x):
    # type: (Any) -> Union[int, str]
    return 1
def f1(x):
    # type: (Any) -> Union[int, str]
    return 'foo'

def f2(x):
    # type: (Any) -> None
    pass
def f2(x,y):
    pass

def f3(x):
    # type: (int) -> int
    return 1+x
def f3(x):
    # type: (int) -> int
    return 'asd'+x

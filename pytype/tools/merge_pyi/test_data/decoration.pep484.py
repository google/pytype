# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
def decoration(func):
    return func

@decoration
def f1(a: t) -> r:
    pass

# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
# tuple unpacking
def f1((a, b)):
    pass

def f1b((a, b)):
    pass

def f2((a, b, (c,d))=(1,2, (3,4))):
    pass

def f3((a, b : int)):
    pass

def f4((a, b : SomeType(a=(3,(4,3))))):
    pass

def f5((((((a,)))))):
    pass

def f6((((((a,)),),))):
    pass

def f7(
        (
        (
        (((a,)),),))):
    pass

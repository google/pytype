import existing_import
from existing_import import d
from m1 import A
from m2 import B
import m3
from m4 import D
from m5.sub import E
from m6 import F
from mStar import *
from m7 import a
from m8 import b
from ......m9 import c

def f(a1, a2, a3, a4, a5, a6):
    # type: (A, B, m3.C, D, E, F) -> G
    pass

def g(a7, a8, a9, a10):
    # type: (a, b, c, d) -> existing_import
    pass

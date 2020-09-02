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

def f(a1: A, a2: B, a3: m3.C, a4: D, a5: E, a6: F) -> G:
    pass

def g(a7: a, a8: b, a9: c, a10: d) -> existing_import:
    pass

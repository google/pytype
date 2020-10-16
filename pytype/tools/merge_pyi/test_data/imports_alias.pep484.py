"""Test import-as."""
from m1 import A_old as A
from m2 import B_old as B
from m3 import C_old as C
import m4_old as m4
import m5.D_old as D
import m5.something.E_old as E

def f(a: A, b: B, c: C, d: D, e: E) -> m4.D:
    pass

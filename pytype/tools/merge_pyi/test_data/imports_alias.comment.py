"""Test import-as."""
from m1 import A_old as A
from m2 import B_old as B
from m3 import C_old as C
import m4_old as m4

def f(a, b, c):
    # type: (A, B, C) -> m4.D
    pass

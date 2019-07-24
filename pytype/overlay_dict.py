"""A dictionary of module names to pytype overlays.

Some libraries need custom overlays to provide useful type information. Pytype
has some built-in overlays, and additional overlays may be added to the overlays
dictionary. See overlay.py for the overlay interface and the *_overlay.py files
for examples.
Each entry in custom_overlays maps the module name to the overlay object
"""

from pytype import abc_overlay
from pytype import asyncio_types_overlay
from pytype import attr_overlay
from pytype import collections_overlay
from pytype import future_overlay
from pytype import six_overlay
from pytype import subprocess_overlay
from pytype import sys_overlay
from pytype import typing_overlay

# Collection of module overlays, used by the vm to fetch an overlay
# instead of the module itself. Memoized in the vm itself.
overlays = {
    "abc": abc_overlay.ABCOverlay,
    "asyncio": asyncio_types_overlay.AsyncioOverlay,
    "attr": attr_overlay.AttrOverlay,
    "collections": collections_overlay.CollectionsOverlay,
    "future.utils": future_overlay.FutureUtilsOverlay,
    "six": six_overlay.SixOverlay,
    "subprocess": subprocess_overlay.SubprocessOverlay,
    "sys": sys_overlay.SysOverlay,
    "types": asyncio_types_overlay.TypesOverlay,
    "typing": typing_overlay.TypingOverlay,
}

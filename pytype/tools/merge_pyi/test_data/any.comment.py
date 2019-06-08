"""Test typing.Any (comment only)."""
import typing
from typing import Any, Text

def f(x, y):
    # type: (Any, Text) -> typing.List
    return []

"""Test return types not matching the return type declaration."""

from __future__ import google_type_annotations


def f() -> int:
  return "foo"

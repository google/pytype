"""Merges type annotations from pyi files into the corresponding py files."""

import difflib
import enum
import shutil

from typing import Optional

import libcst as cst
from libcst import codemod
from libcst.codemod import visitors


def _merge_trees(*, py_tree, pyi_tree):
  context = codemod.CodemodContext()
  vis = visitors.ApplyTypeAnnotationsVisitor
  vis.store_stub_in_context(context, pyi_tree)
  return vis(
      context,
      strict_posargs_matching=False,
      strict_annotation_matching=True,
  ).transform_module(py_tree)


def merge_sources(*, py, pyi):
  py_cst = cst.parse_module(py)
  pyi_cst = cst.parse_module(pyi)
  merged_cst = _merge_trees(py_tree=py_cst, pyi_tree=pyi_cst)
  return merged_cst.code


class Mode(enum.Enum):
  PRINT = 1
  DIFF = 2
  OVERWRITE = 3


def _get_diff(a, b):
  a, b = a.split("\n"), b.split("\n")
  diff = difflib.Differ().compare(a, b)
  return "\n".join(diff)


def merge_files(
    *,
    py_path: str,
    pyi_path: str,
    mode: Mode,
    backup: Optional[str] = None
) -> bool:
  """Merges a .py and a .pyi file."""

  with open(py_path, "r") as f:
    py_src = f.read()
  with open(pyi_path, "r") as f:
    pyi_src = f.read()
  annotated_src = merge_sources(py=py_src, pyi=pyi_src)
  changed = annotated_src != py_src
  if mode == Mode.PRINT:
    # Always print to stdout even if we haven't changed anything.
    print(annotated_src)
  elif mode == Mode.DIFF and changed:
    diff = _get_diff(py_src, annotated_src)
    print(diff)
  elif mode == Mode.OVERWRITE and changed:
    if backup:
      shutil.copyfile(py_path, f"{py_path}.{backup}")
    with open(py_path, "w") as f:
      f.write(annotated_src)
  return changed

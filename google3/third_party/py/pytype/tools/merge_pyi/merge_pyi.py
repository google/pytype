"""Merges type annotations from pyi files into the corresponding py files."""

import difflib
import enum
import os
import shutil

from typing import List, Optional, Tuple

import libcst as cst
from libcst import codemod
from libcst.codemod import visitors
from pytype.platform_utils import path_utils


class MergeError(Exception):
  """Wrap exceptions thrown while merging files."""


def _merge_csts(*, py_tree, pyi_tree):
  context = codemod.CodemodContext()
  vis = visitors.ApplyTypeAnnotationsVisitor
  vis.store_stub_in_context(context, pyi_tree)
  return vis(
      context,
      strict_posargs_matching=False,
      strict_annotation_matching=True,
  ).transform_module(py_tree)


def merge_sources(*, py, pyi):
  try:
    py_cst = cst.parse_module(py)
    pyi_cst = cst.parse_module(pyi)
    merged_cst = _merge_csts(py_tree=py_cst, pyi_tree=pyi_cst)
    return merged_cst.code
  except Exception as e:  # pylint: disable=broad-except
    raise MergeError(str(e)) from e


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

  with open(py_path) as f:
    py_src = f.read()
  with open(pyi_path) as f:
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


def merge_tree(
    *,
    py_path: str,
    pyi_path: str,
    backup: Optional[str] = None,
    verbose: bool = False
) -> Tuple[List[str], List[Tuple[str, MergeError]]]:

  """Merge .py files in a tree with the corresponding .pyi files."""

  errors = []
  changed_files = []

  for root, _, files in os.walk(py_path):
    rel = path_utils.relpath(py_path, root)
    pyi_dir = path_utils.normpath(path_utils.join(pyi_path, rel))
    for f in files:
      if f.endswith(".py"):
        py = path_utils.join(root, f)
        pyi = path_utils.join(pyi_dir, f + "i")
        if path_utils.exists(pyi):
          if verbose:
            print("Merging:", py, end=" ")
          try:
            changed = merge_files(
                py_path=py, pyi_path=pyi, mode=Mode.OVERWRITE, backup=backup)
            if changed:
              changed_files.append(py)
            if verbose:
              print("[OK]")
          except MergeError as e:
            errors.append((py, e))
            if verbose:
              print("[FAILED]")
  return changed_files, errors

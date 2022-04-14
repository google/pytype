"""Merges type annotations from pyi files int the corresponding source files."""

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

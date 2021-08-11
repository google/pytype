"""LibCST-based function signature merging."""

from typing import List, Tuple, Dict, Optional

import libcst as cst

AnnotationKey = Tuple[str, ...]

AnnotationType = Dict[
    AnnotationKey,  # key: tuple of canonical class/function name
    Tuple[cst.Parameters, Optional[cst.Annotation]],  # val: (params, returns)
]


class TypingCollector(cst.CSTVisitor):
  """Collect type annotations from pyi source code."""

  def __init__(self):
    # stack for storing the canonical name of the current function
    self.stack: List[str] = []
    # store the annotations
    self.annotations: AnnotationType = {}

  def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
    self.stack.append(node.name.value)

  def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
    self.stack.pop()

  def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
    self.stack.append(node.name.value)
    self.annotations[tuple(self.stack)] = (node.params, node.returns)
    # pyi doesn't support inner functions, return False to stop the traversal.
    return False

  def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
    self.stack.pop()


class TypingTransformer(cst.CSTTransformer):
  """Merge annotations into python source code."""

  def __init__(self, annotations: AnnotationType):
    # stack for storing the canonical name of the current function
    self.stack: List[str] = []
    # store the annotations
    self.annotations: AnnotationType = annotations

  def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
    self.stack.append(node.name.value)

  def leave_ClassDef(
      self, original_node: cst.ClassDef, updated_node: cst.ClassDef
  ) -> cst.CSTNode:
    self.stack.pop()
    return updated_node

  def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
    self.stack.append(node.name.value)
    # pyi doesn't support inner functions, return False to stop the traversal.
    return False

  def leave_FunctionDef(
      self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
  ) -> cst.CSTNode:
    key = tuple(self.stack)
    self.stack.pop()
    if key in self.annotations:
      annotations = self.annotations[key]
      params, returns = annotations
      return updated_node.with_changes(params=params, returns=returns)
    return updated_node


def _merge_trees(*, py_tree, pyi_tree):
  visitor = TypingCollector()
  pyi_tree.visit(visitor)
  transformer = TypingTransformer(visitor.annotations)
  modified_tree = py_tree.visit(transformer)
  return modified_tree


def merge_sources(*, py_src, pyi_src):
  source_cst = cst.parse_module(py_src)
  stub_cst = cst.parse_module(pyi_src)
  merged_cst = _merge_trees(py_tree=source_cst, pyi_tree=stub_cst)
  return merged_cst.code

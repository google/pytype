"""Representation of variable annotations and typecomments in source code."""

import dataclasses

from typing import Dict, Optional


@dataclasses.dataclass(frozen=True)
class VariableAnnotation:
  """Store a variable annotation or typecomment."""
  name: Optional[str]
  annotation: str


class VariableAnnotations:
  """Store variable annotations and typecomments for a program."""

  def __init__(self):
    self.variable_annotations: Dict[int, VariableAnnotation] = {}
    self.type_comments: Dict[int, str] = {}

  def add_annotation(self, line: int, name: str, annotation: str):
    self.variable_annotations[line] = VariableAnnotation(name, annotation)

  def add_type_comment(self, line: int, annotation: str):
    self.type_comments[line] = annotation

  @property
  def annotations(self) -> Dict[int, VariableAnnotation]:
    # It's okay to overwrite type comments with variable annotations here
    # because _FindIgnoredTypeComments in vm.py will flag ignored comments.
    ret = {k: VariableAnnotation(None, v)
           for k, v in self.type_comments.items()}
    ret.update(self.variable_annotations)
    return ret

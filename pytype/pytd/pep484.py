"""PEP484 compatibility code."""

import re

from pytype.pytd.parse import visitors


class Print484StubVisitor(visitors.Visitor):
  """Visitor for converting ASTs to the PEP 484 format.

  This generates a PEP484 "stub" format that contains function signatures, but
  no code. For example:
    class MyList(GenericType[T]):
      def append(self, x: T) -> NoneType: pass
  """
  visits_all_node_types = True
  INDENT = " " * 4

  def _SafeName(self, name):
    if not re.match(r"^[a-zA-Z_]", name):
      name = "_" + name
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)

  def _MaybeCapitalize(self, s):
    """Capitalize container types.

    PEP484 defines some container types in "typing.py". E.g. "List" or "Dict".
    If we have a base type that corresponds to that, convert it to the
    corresponding PEP484 name.
    Args:
      s: A type name, e.g. "int" or "list"
    Returns:
      A type name that can be used as a PEP 484 generic. E.g. "List".
    """
    if s in ["list", "tuple", "dict"]:
      return s.capitalize()
    else:
      return s

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module to a PEP484 stub."""
    sections = [node.constants, node.functions, node.classes]
    sections_as_string = ("\n".join(section_suite)
                          for section_suite in sections
                          if section_suite)
    return "\n\n".join(sections_as_string)

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    return self._SafeName(node.name) + " = Undefined(" + node.type + ")"

  def VisitClass(self, node):
    """Visit a class, producing a multi-line, properly indented string."""
    parents = list(node.parents)
    if node.template:
      parents += ["GenericType[%s]" % ", ".join(node.template)]
    header = "class " + self._SafeName(node.name)
    if parents:
      header += "(" + ", ".join(parents) + ")"
    header += ":"
    if node.methods or node.constants:
      constants = [self.INDENT + m for m in node.constants]
      method_lines = sum((m.splitlines() for m in node.methods), [])
      methods = [self.INDENT + m for m in method_lines]
    else:
      constants = []
      methods = [self.INDENT + "pass"]
    return "\n".join([header] + constants + methods) + "\n"

  def VisitFunction(self, node):
    """Visit function, producing multi-line string (one for each signature)."""
    overload = "@overload\n" if len(node.signatures) > 1 else ""
    function_name = self._SafeName(node.name)
    return "\n".join(overload + "def " + function_name + sig
                     for sig in node.signatures)

  def VisitSignature(self, node):
    """Visit a signature, producing a string."""
    template = "<" + ", ".join(node.template) + ">" if node.template else ""
    ret = " -> " + node.return_type

    optional = ("*args, **kwargs",) if node.has_optional else ()

    body = ":"
    if node.exceptions:
      body += "\n"
      for exc in node.exceptions:
        body += self.INDENT + "raise %s()\n" % exc
    else:
      body += " pass\n"  # put 'pass' into the same line

    return "%s(%s)%s%s" % (template, ", ".join(node.params + optional),
                           ret, body)

  def VisitParameter(self, node):
    """Convert a function parameter to a string."""
    if node.type == "object":
      # Abbreviated form. "object" is the default.
      return node.name
    elif node.name == "self":
      return "self"
    else:
      return self._SafeName(node.name) + ": " + node.type

  def VisitOptionalParameter(self, node):
    """Convert a optional function parameter to a string."""
    return self.VisitParameter(node) + " = ..."

  def VisitMutableParameter(self, node):
    """Convert a mutable function parameter to a string."""
    return self.VisitParameter(node)

  def VisitTemplateItem(self, node):
    """Convert a template to a string."""
    return node.type_param

  def VisitNamedType(self, node):
    """Convert a type to a string."""
    return self._SafeName(node.name)

  def VisitNativeType(self, node):
    """Convert a native type to a string."""
    return self._SafeName(node.python_type.__name__)

  def VisitAnythingType(self, unused_node):
    """Convert an anything type to a string."""
    return "Any"

  def VisitNothingType(self, unused_node):
    """Convert the nothing type to a string."""
    return "Nothing"

  def VisitClassType(self, node):
    return self._SafeName(node.name)

  def VisitTypeParameter(self, node):
    return self._SafeName(node.name)

  def VisitHomogeneousContainerType(self, node):
    """Convert a homogeneous container type to a string."""
    return self.VisitGenericType(node)

  def VisitGenericType(self, node):
    """Convert a generic type (E.g. list[int]) to a string."""
    param_str = ", ".join(node.parameters)
    return self._MaybeCapitalize(node.base_type) + "[" + param_str + "]"

  def VisitUnionType(self, node):
    """Convert a union type ("x or y") to a string."""
    return "Union[%s]" % ", ".join(node.type_list)

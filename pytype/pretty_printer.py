"""A printer for human-readable output in error messages etc."""

from pytype.abstract import abstract


def show_constant(val: abstract.BaseValue) -> str:
  """Pretty-print a value if it is a constant.

  Recurses into a constant, printing the underlying Python value for constants
  and just using "..." for everything else (e.g., Variables). This is useful for
  generating clear error messages that show the exact values related to an error
  while preventing implementation details from leaking into the message.

  Args:
    val: an abstract value.

  Returns:
    A string of the pretty-printed constant.
  """
  def _ellipsis_printer(v):
    if isinstance(v, abstract.PythonConstant):
      return v.str_of_constant(_ellipsis_printer)
    return "..."
  return _ellipsis_printer(val)



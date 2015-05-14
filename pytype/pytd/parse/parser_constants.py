"""Parser constants that are used by parser.py and visitors.py."""

import re

RESERVED = [
    # Python keywords that are used by PyTD:
    'and',
    'class',
    'def',
    'else',
    'if',
    'or',
    'pass',
    # Keywords that are valid identifiers in Python (PyTD keywords):
    'PYTHONCODE',  # upper-case: stands out + unlikely name
    'nothing',
    'raises',
    # 'strict',  # TODO(pludemann): add
    ]

RESERVED_PYTHON = [
    # Python keywords that aren't used by PyTD:
    'as',
    'assert',
    'break',
    'continue',
    'del',
    'elif',
    'except',
    'exec',
    'finally',
    'for',
    'from',
    'global',
    'import',
    'in',
    'is',
    'lambda',
    'not',
    # 'print',  # Not reserved in Python3
    'raise',
    'return',
    'try',
    'while',
    'with',
    'yield',
    ]

# parser.t_NAME's regexp allows a few extra characters in the name.
# A less-pedantic RE is r'[-~]'.
# See visitors._EscapedName and parser.PyLexer.t_NAME
BACKTICK_NAME = re.compile(r'[-]|^~')

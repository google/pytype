"""Parser constants that are used by parser.py and visitors.py."""

import re


from pytype.pytd import pytd

PEP484_TRANSLATIONS = {
    # PEP 484 allows 'None' as an abbreviation of 'NoneType'.
    'None': pytd.NamedType('NoneType'),
    # PEP 484 definitions of built-in types:
    'List': pytd.NamedType('list'),
    'Dict': pytd.NamedType('dict'),
    'Tuple': pytd.NamedType('tuple'),
    'Set': pytd.NamedType('set'),
    'Generator': pytd.NamedType('generator'),
    # PEP 484 definitions of special purpose types:
    'Any': pytd.AnythingType(),
    # TODO(kramm): 'typing.NamedTuple'
}

# PyTD keywords
RESERVED = [
    'and',
    'class',
    'def',
    'else',
    'if',
    'or',
    'pass',
    'import',
    'from',
    'as',
    # Keywords that are valid identifiers in Python (PyTD keywords):
    'PYTHONCODE',  # upper-case: stands out + unlikely name
    'nothing',
    'raises',
    # Names from typing.py
    'TypeVar',
    ]

RESERVED_PYTHON = [
    # Python keywords that aren't used by PyTD:
    'assert',
    'break',
    'continue',
    'del',
    'elif',
    'except',
    'exec',
    'finally',
    'for',
    'global',
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

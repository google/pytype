"""Parser constants that are used by parser.py and visitors.py."""

import re


from pytype.pytd import pytd

PEP484_CAPITALIZED = {
    # The PEP 484 definition of these built-in types is the capitalized name.
    # E.g. "List" to represent the "list" type.
    'list', 'dict', 'tuple', 'set', 'generator', 'iterator'
}
PEP484_TRANSLATIONS = {
    # PEP 484 allows 'None' as an abbreviation of 'NoneType'.
    'None': pytd.NamedType('NoneType'),
    # PEP 484 definitions of special purpose types:
    'Any': pytd.AnythingType(),
    'AnyStr': pytd.UnionType((tuple('str'), tuple('unicode'))),
    # TODO(kramm): 'typing.NamedTuple'
}
PEP484_TRANSLATIONS.update({name.capitalize(): pytd.NamedType(name)
                            for name in PEP484_CAPITALIZED})

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
    'raise',
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

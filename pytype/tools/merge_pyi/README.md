Copy type annotations from a PEP484 stub file into python source.

This script is Python 2 and 3 compatible.

## Sample uses:

Add the type annotations in simple.pyi to simple.py and print the updated file
to stdout:

       merge-pyi testdata/simple.py testdata/simple.pyi

Add the type annotations in simple.pyi to simple.py as type comments:

       merge-pyi --as-comments testdata/simple.py testdata/simple.pyi

Output a diff of the changes to the source file:

       merge-pyi --diff testdata/simple.py testdata/simple.pyi

Overwrite the source file:

       merge-pyi -i testdata/simple.py testdata/simple.pyi

#### Regression tests

```
testdata/foo.py  : input we want to annotate
testdata/foo.pyi : type hints we want to add to foo.py (may be intentionally bad)

testdata/foo.comment.py : expected output, inserting types as comments
testdata/foo.pep484.py  : expected output, inserting types in PEP484 style
```

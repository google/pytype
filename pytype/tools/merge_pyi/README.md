Copy type annotations from a PEP484 stub file into python source.

This script is Python 2 and 3 compatible.

## Sample uses:

Print to stdout what simple.py would look like with the type annotations from
simple.pyi added:

       merge-pyi test_data/simple.py test_data/simple.pyi

Print to stdout what simple.py would look like with the type annotations from
simple.pyi added as type comments:

       merge-pyi --as-comments test_data/simple.py test_data/simple.pyi

Output a diff of the changes to simple.py:

       merge-pyi --diff test_data/simple.py test_data/simple.pyi

Overwrite simple.py:

       merge-pyi -i test_data/simple.py test_data/simple.pyi

#### Regression tests

```
test_data/foo.py  : input we want to annotate
test_data/foo.pyi : type hints we want to add to foo.py (may be intentionally bad)

test_data/foo.comment.py : expected output, inserting types as comments
test_data/foo.pep484.py  : expected output, inserting types in PEP484 style
```

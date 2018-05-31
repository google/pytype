This is not an official Google product.

Copy type annotations from a PEP484 stub file into python source.

This script is Python 2 and 3 compatible.

## Sample uses:

Add the type annotations in simple.pyi to simple.py and print the updated file
to stdout:

       python merge_pyi.py testdata/simple.py testdata/simple.pyi

Add the type annotations in simple.pyi to simple.py as type comments:

       python merge_pyi.py --as-comments testdata/simple.py testdata/simple.pyi

Output a diff of the changes to the source file:

       python merge_pyi.py --diff testdata/simple.py testdata/simple.pyi

Overwrite the source file:

       python merge_pyi.py -i testdata/simple.py testdata/simple.pyi

[PyCon 2016 slides](https://docs.google.com/a/google.com/presentation/d/1S3Pa-6ogG-yNcQpbU-JrhiFEHNtw_8laF1svOekuYOI/pub?start=false&loop=false&delayms=3000)

#### Regression tests

```
testdata/foo.py  : input we want to annotate
testdata/foo.pyi : type hints we want to add to foo.py (may be intentionally bad)

testdata/foo.comment.py : expected output, inserting types as comments
testdata/foo.pep484.py  : expected output, inserting types in PEP484 style
```

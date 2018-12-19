# Pytype Functional Tests

This directory contains functional tests for Pytype. Please read the rest of
this file before adding new tests.

## Definitions

* **Target**: Python code analyzed by Pytype.
* **Target Version**: The version of the Python code analyzed by Pytype.

## Organization

The tests in this directory are grouped into three logical buckets:

1. Target Independent Bucket: Tests of this kind live in the top level of this
directory. They do not depend on any specific feature from the target's version.
They also should not use type annotations in the target code. The test classes
for these tests are subclasses of `TargetIndependentTest`. These tests are
run multiple times, once with target version set to 2.7, and another time per
target Python 3 version supported.

2. The Py2 Feature Bucket: Tests of this kind live in the `py2`
subdirectory. The target code for these tests uses a Python 2.7 specific
feature. The test classes for these tests are subclasses of
`TargetPython27FeatureTest`.

3. The Py3 Basic Bucket: Tests of this kind live in the `py3` subdirectory.
The target code for these tests uses type annotations as the only Python 3
specific feature. Without the type annotations, the target should be version
agnostic. The test classes for these tests are subclasses of
`TargetPython3BasicTest`.

4. The Py3 Feature Bucket: Tests of this kind also live in the `py3`
subdirectory. The target code for these tests uses a Python 3 specific feature,
with or without type annotations. The test classes for these tests are
subclasses of `TargetPython3FeatureTest`.

## Adding New Tests

Adding a new test method to an existing functional test class is straight
forward and does not need any special care. Adding a new test class, however,
should be done under the following rules:

1. A new test class should subclass one of the above base classes.
2. If a new test module is being added, then it should be added to one of the
above buckets. Also, it should unconditionally call the `test_base.main`
function as follows:
```
test_base.main(globals(), __name__ == "__main__")
```

# Python version upgrades

This doc contains instructions for how to upgrade pytype to support a new Python
version, using the Python 3.6->3.7 upgrade as an example.

## pytype

The process is as follows:

1. Build pytype in the new version, so that you can try out your changes. Have a
   test file, such as [pytype/test_data/simple.py][test_data.simple], handy.
   For the open-source build, first [update setup.cfg](#github_release) (only
   locally for now!), then
   [install from source](https://github.com/google/pytype#installing) using the
   new version's pip.
1. Make the [minimal changes](#minimal_changes) for pytype to start analyzing
   code in the new version.
1. Run the [regression tests](#regression_tests) and fix failures.
1. [Update setup.cfg](#github_release) to declare support for the new version.
   Even though any new features have not yet been implemented, we can start
   offering type-checking for backwards-compatible code.
1. Implement [new features](#new_features).

### minimal changes

#### version validation
The [pytype.utils.validate_version][utils.validate_version] method should be
updated to accept the new version.

#### opcode changes

If the new version adds or removes any opcodes, then an updated opcode mapping
should be added to
[pytype/pyc/opcodes.py][pyc.opcodes.python_3_7_mapping] and new opcodes
implemented in [pytype/vm.py][vm.VirtualMachine.byte_LOAD_METHOD].

The [documentation](https://docs.python.org/3/library/dis.html) for the dis
library is a good reference for bytecode changes.

#### magic numbers

Magic numbers for the new version should be copied from the
[CPython source code][cpython-source] to [pytype/pyc/magic.py][pyc.magic].

### regression tests

For the open-source project, navigate to the root of your cloned pytype
repository and run using the new Python version:

```
python build_scripts/run_tests.py
```

The new version should also be added to the
[Travis test matrix](
https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/.travis.yml#L9).
Even if the tests do not pass yet, it is helpful to see the failures, and you
can configure them to not fail the build by adding to the matrix:

```
allow_failures:
  - python: "3.x"  # replace x with the appropriate minor version
```

### GitHub release

Update the `classifiers` and `install_requires` fields in
[setup.cfg](https://github.com/google/pytype/blob/master/setup.cfg) to include
the new version.

### new features

Changes may be needed to pytype to support new features that affect typing. For
3.7, such features included postponed evaluation of type annotations,
dataclasses, and typing.OrderedDict. New features can be found on the
["What's New in Python 3.x" page](https://docs.python.org/3/whatsnew/3.7.html)
and by searching for "New in version 3.x" in the
[typing module documentation](https://docs.python.org/3/library/typing.html).

<!-- References with different internal and external versions -->

[cpython-source]: https://github.com/python/cpython/blob/beba1a808000d5fc445cb28eab96bdb4cdb7c959/Lib/importlib/_bootstrap_external.py#L245

[pyc.magic]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/pyc/magic.py#L97

[pyc.opcodes.python_3_7_mapping]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/pyc/opcodes.py#L1101

[test_data.simple]: https://github.com/google/pytype/blob/master/pytype/test_data/simple.py

[utils.validate_version]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/utils.py#L74

[vm.VirtualMachine.byte_LOAD_METHOD]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/vm.py#L3128

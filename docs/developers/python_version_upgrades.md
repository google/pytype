# Python version upgrades

<!--* freshness: { exempt: true } *-->

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
   We can start offering type-checking for backwards-compatible code, even
   before any new features have been implemented.
1. Implement [new features](#new_features).

### minimal changes

#### version validation
The [pytype.utils.validate_version][utils.validate_version] method should be
updated to accept the new version.

#### opcode changes

If the new version adds or removes any opcodes, then updated opcodes should be
added to [pytype/pyc/opcodes.py][pyc.opcodes], an opcode mapping to
[pycnite/mapping.py][pycnite.mapping] and new opcodes implemented in
[pytype/vm.py][vm.VirtualMachine.byte_LOAD_METHOD].

TIP: [pytype/pyc/generate_opcode_diffs.py][pyc.generate_opcode_diffs] will
generate the changes you need to make to opcodes.py, as well as
stub implementations for vm.py.

If the above script doesn't work, you can figure out the necessary changes by
playing around with the [opcode][cpython-opcode] library:

* `opcode.opmap` contains a name->index mapping of all opcodes.
* Opcodes with an index of at least `opcode.HAVE_ARGUMENT` have an argument.
* The `opcode.has{property}` attributes correspond to `HAS_{PROPERTY}` flags in
  pytype's opcodes module.

The [documentation](https://docs.python.org/3/library/dis.html) for the dis
library is a good reference for bytecode changes. dis is also handy for
disassembling a piece of code and comparing the bytecode between two versions.
For example, to disassemble a function `foo.f`:

```python
import dis
import foo
dis.dis(foo.f)  # pretty-prints the bytecode to stdout
```

Finally, if all else fails, you can consult the [CPython source code](
https://github.com/python/cpython/blob/master/Python/ceval.c).

#### magic numbers

Magic numbers for the new version should be copied from the
[CPython source code][cpython-source] to [pycnite/magic.py][pycnite.magic].

#### stubs

We maintain custom pytd stubs for some modules in
[pytype/stubs/{builtins,stdlib}][stubs]. Compare them to the
[typeshed versions][typeshed] and make sure all types for the new Python version
are present in our stubs.

### regression tests

For the open-source project, navigate to the root of your cloned pytype
repository and run using the new Python version:

```
python build_scripts/run_tests.py
```

The new version should also be added to the
[CI test matrix](
https://github.com/google/pytype/blob/a2ce16edc0ee992f97b328ce752b51318a00d513/.github/workflows/ci.yml#L15-L22).
Even if the tests do not pass yet, it is helpful to see the failures. You can
can configure them to not fail the workflow by [marking the check as experimental](
https://github.com/google/pytype/blob/a2ce16edc0ee992f97b328ce752b51318a00d513/.github/workflows/ci.yml#L19-L22)
<!-- TODO(rechen): Once https://github.com/actions/toolkit/issues/399 is
supported, suggest that instead of the `|| exit 0` hack -->
and using `|| exit 0` to [always report a success](
https://github.com/google/pytype/blob/a2ce16edc0ee992f97b328ce752b51318a00d513/.github/workflows/ci.yml#L47-L49).

### GitHub release

Update the `classifiers` and `install_requires` fields in
[setup.cfg](https://github.com/google/pytype/blob/main/setup.cfg) to include
the new version.

### new features

Changes may be needed to pytype to support new features that affect typing. For
3.7, such features included postponed evaluation of type annotations,
dataclasses, and typing.OrderedDict. New features can be found on the
["What's New in Python 3.x" page](https://docs.python.org/3/whatsnew/3.7.html)
and by searching for "New in version 3.x" in the
[typing module documentation](https://docs.python.org/3/library/typing.html).

[cpython-opcode]: https://github.com/python/cpython/blob/master/Lib/opcode.py

<!-- References with different internal and external versions -->
<!-- mdformat off(mdformat adds/removes newlines, which make these harder to read) -->

[cpython-source]: https://github.com/python/cpython/blob/beba1a808000d5fc445cb28eab96bdb4cdb7c959/Lib/importlib/_bootstrap_external.py#L245

[pyc.generate_opcode_diffs]: https://github.com/google/pytype/blob/main/pytype/pyc/generate_opcode_diffs.py

[pyc.opcodes]: https://github.com/google/pytype/blob/6516ebd5def4ac507a5449b0c57297a53b7e9a9f/pytype/pyc/opcodes.py#L201-L1018

[pycnite.mapping]: https://github.com/google/pycnite/blob/25326a096278a8372e03bbefab8fa4b725f96245/pycnite/mapping.py#L196

[pycnite.magic]: https://github.com/google/pycnite/blob/25326a096278a8372e03bbefab8fa4b725f96245/pycnite/magic.py#L20

[stubs]: https://github.com/google/pytype/tree/main/pytype/stubs

[typeshed]: https://github.com/python/typeshed

[test_data.simple]: https://github.com/google/pytype/blob/main/pytype/test_data/simple.py

[utils.validate_version]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/utils.py#L74

[vm.VirtualMachine.byte_LOAD_METHOD]: https://github.com/google/pytype/blob/ee51995a1c5937cb4ebee291acb2e049fb0f81cc/pytype/vm.py#L3128

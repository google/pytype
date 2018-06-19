[![Build Status](https://travis-ci.org/google/pytype.svg?branch=master)](https://travis-ci.org/google/pytype)

## Pytype

Statically check and infer types for unannotated Python code.
(This is not an official Google product.)

## Abstract

Pytype is a static analyzer that helps you find type errors in Python code. It
can type-check code with or without
[type annotations](https://www.python.org/dev/peps/pep-0484/), as well as
generate annotations. Pytype runs under Python 2.7 or 3.6 and analyzes both
Python 2 and Python 3 code.

## Example

Below, `print_greeting` calls `make_greeting` incorrectly:

```
$ cat foo.py

def make_greeting(user_id):
    return 'hello, user' + user_id

def print_greeting():
    print(make_greeting(0))
```

Run pytype to catch the bug:

```
$ pytype foo.py

File "foo.py", line 2, in make_greeting: Function str.__add__ was called with the wrong arguments [wrong-arg-types]
  Expected: (self, y: str)
  Actually passed: (self, y: int)
Traceback:
  line 5, in print_greeting
```

Merge pytype's generated type information back into `foo.py`:

```
$ cat pytype_output/foo.pyi

def make_greeting(user_id) -> str: ...
def print_greeting() -> None: ...

$ merge-pyi -i foo.py foo.pyi
$ cat foo.py

def make_greeting(user_id) -> str:
    return 'hello, user' + user_id

def print_greeting() -> None:
    print(make_greeting(0))
```

## Requirements

You need a Python 2.7 or 3.6 interpreter to run pytype, as well as an
interpreter in `$PATH` for the Python version of the code you're analyzing.

Platform support:

* Pytype is currently developed and tested on Linux, which is the main supported
  platform.
* Installation on MacOSX requires OSX 10.7 or higher and Xcode v8 or higher.
* Windows is currently not supported.

## Quickstart resources

The rest of this document provides complete instructions for installing and
using pytype. To quickly get started with some common workflows, check out the
following docs:

* [Quickstart](
   https://github.com/google/pytype/tree/master/docs/quickstart.md)
* [Error classes](
   https://github.com/google/pytype/tree/master/docs/errors.md)

## Installing

Pytype can be installed via pip. Note that the installation requires `wheel`
and `setuptools`. (If you're working in a virtualenv, these two packages should
already be present.)

```
pip install pytype
```

Or from the source code [on GitHub](https://github.com/google/pytype/).

```
git clone --recurse-submodules https://github.com/google/pytype.git
cd pytype
pip install -U .
```

Instead of using `--recurse-submodules`, you could also have run

```
git submodule init
git submodule update
```

in the `pytype` directory.

## Usage

```
usage: pytype [options] input [input ...]

positional arguments:
  input                 file or directory to process
```

Common options:

* `-V, --python-version`: Python version (major.minor) of the target code.
  Defaults to `3.6`.
* `-o, --output`: The directory into which all pytype output goes, including
  generated .pyi files. Defaults to `pytype_output`.
* `-P, --pythonpath`. Paths to source code directories, separated by ':'.
  Defaults to an educated guess based on `input`.
* `-d, --disable`. Comma separated list of error names to ignore. Detailed
  explanations of pytype's error names are in
  [this doc](https://github.com/google/pytype/tree/master/docs/errors.md).
  Defaults to empty.

For a full list of options, run `pytype --help`.

In addition to the above, you can direct pytype to use a custom typeshed
installation instead of its own bundled copy by setting `$TYPESHED_HOME`.

### Config File

For convenience, you can save your pytype configuration in a file. The config
file is an INI-style file with a `[pytype]` section; if an explicit config file
is not supplied, pytype will look for a `[pytype]` section in the first
`setup.cfg` file found by walking upwards from the current working directory.

Start off by generating a sample config file:

```
$ pytype --generate-config pytype.cfg
```

Now customize the file based on your local setup, keeping only the sections you
need. Directories may be relative to the location of the config file, which is
useful if you want to check in the config file as part of your project.

For example, suppose you have the following directory structure and want to
analyze package `~/repo1/foo`, which depends on package `~/repo2/bar`:

```
~/
├── repo1
│   └── foo
│       ├── __init__.py
│       └── file_to_check.py
└── repo2
    └── bar
        ├── __init__.py
        └── dependency.py
```

Here is the filled-in config file, which instructs pytype to treat its input as
Python 3.6 code and ignore attribute errors. Notice that the path to a package
does not include the package itself.

```
$ cat ~/repo1/pytype.cfg

# NOTE: All relative paths are relative to the location of this file.

[pytype]
# Python version (major.minor) of the target code.
python_version = 3.6

# Paths to source code directories, separated by ':'.
pythonpath =
    .:
    ~/repo2

disable=attribute-error
```

We could've discovered that `~/repo2` needed to be added to the pythonpath by
running pytype's broken dependency checker:

```
$ pytype --config=~/repo1/pytype.cfg ~/repo1/foo/*.py --unresolved

Unresolved dependencies:
  bar.dependency
```

### Subtools

Pytype ships with three scripts in addition to `pytype` itself:

* [`merge-pyi`](
https://github.com/google/pytype/tree/master/pytype/tools/merge_pyi/README.md),
for merging type information from a .pyi file into a Python file.
* `pytd`, a parser for .pyi files.
* `pytype-single`, a debugging tool for pytype developers, which analyzes a
single Python file assuming that .pyi files have already been generated for all
of its dependencies.

## Roadmap

* Windows support
* A rerun mode to only reanalyze files that have changed since the last run

## License
Apache 2.0

Pytype
======

Pytype checks and infers types for your Python code - without requiring
type annotations. Pytype can:

-  Lint plain Python code, flagging common mistakes such as mispelled
   attribute names, incorrect function calls, and `much
   more <docs/errors.md>`__, even across file boundaries.
-  Enforce user-provided `type
   annotations <https://www.python.org/dev/peps/pep-0484>`__. While
   annotations are optional for pytype, it will check and apply them
   where present.
-  Generate type annotations in standalone files ("`pyi
   files <docs/user_guide.md#pyi-stub-files>`__"), which can be merged
   back into the Python source with a provided
   `merge-pyi <https://github.com/google/pytype/tree/master/pytype/tools/merge_pyi>`__
   tool.

Pytype is a static analyzer, meaning it does not execute the code it
runs on.

Thousands of projects at Google rely on pytype to keep their Python code
well-typed and error-free.

For more information, check out the `user guide <docs/user_guide.md>`__
or `FAQ <docs/faq.md>`__.

Quickstart
----------

To quickly get started with type-checking a file or directory, run the
following, replacing ``file_or_directory`` with your input:

::

    pip install pytype
    pytype file_or_directory

To set up pytype on an entire package, add the following to a
``setup.cfg`` file in the directory immediately above the package,
replacing ``package_name`` with the package name:

::

    [pytype]
    inputs = package_name

Now you can run the no-argument command ``pytype`` to type-check the
package. It's also easy to add pytype to your automated testing; see
this
`example <https://github.com/google/importlab/blob/master/.travis.yml>`__
of a GitHub project that runs pytype on Travis.

Finally, pytype generates files of inferred type information, located by
default in ``.pytype/pyi``. You can use this information to
type-annotate the corresponding source file, replacing ``module.py``
with the file's import path:

::

    merge-pyi -i module.py .pytype/pyi/module.pyi

Requirements
------------

You need a Python 2.7 or 3.5+ interpreter to run pytype, as well as an
interpreter in ``$PATH`` for the Python version of the code you're
analyzing.

Platform support:

-  Pytype is currently developed and tested on Linux, which is the main
   supported platform.
-  Installation on MacOSX requires OSX 10.7 or higher and Xcode v8 or
   higher.
-  Windows is currently not supported.

Installing
----------

Pytype can be installed via pip. Note that the installation requires
``wheel`` and ``setuptools``. (If you're working in a virtualenv, these
two packages should already be present.)

::

    pip install pytype

Or from the source code `on
GitHub <https://github.com/google/pytype/>`__.

::

    git clone --recurse-submodules https://github.com/google/pytype.git
    cd pytype
    pip install -U .

Instead of using ``--recurse-submodules``, you could also have run

::

    git submodule init
    git submodule update

in the ``pytype`` directory.

Usage
-----

::

    usage: pytype [options] input [input ...]

    positional arguments:
      input                 file or directory to process

Common options:

-  ``-V, --python-version``: Python version (major.minor) of the target
   code. Defaults to ``3.6``.
-  ``-o, --output``: The directory into which all pytype output goes,
   including generated .pyi files. Defaults to ``.pytype``.
-  ``-d, --disable``. Comma separated list of error names to ignore.
   Detailed explanations of pytype's error names are in `this
   doc <docs/errors.md>`__. Defaults to empty.

For a full list of options, run ``pytype --help``.

In addition to the above, you can direct pytype to use a custom typeshed
installation instead of its own bundled copy by setting
``$TYPESHED_HOME``.

Config File
~~~~~~~~~~~

For convenience, you can save your pytype configuration in a file. The
config file is an INI-style file with a ``[pytype]`` section; if an
explicit config file is not supplied, pytype will look for a
``[pytype]`` section in the first ``setup.cfg`` file found by walking
upwards from the current working directory.

Start off by generating a sample config file:

::

    $ pytype --generate-config pytype.cfg

Now customize the file based on your local setup, keeping only the
sections you need. Directories may be relative to the location of the
config file, which is useful if you want to check in the config file as
part of your project.

For example, suppose you have the following directory structure and want
to analyze package ``~/repo1/foo``, which depends on package
``~/repo2/bar``:

::

    ~/
    ├── repo1
    │   └── foo
    │       ├── __init__.py
    │       └── file_to_check.py
    └── repo2
        └── bar
            ├── __init__.py
            └── dependency.py

Here is the filled-in config file, which instructs pytype to type-check
``~/repo1/foo`` as Python 3.6 code, look for packages in ``~/repo1`` and
``~/repo2``, and ignore attribute errors. Notice that the path to a
package does not include the package itself.

::

    $ cat ~/repo1/pytype.cfg

    # NOTE: All relative paths are relative to the location of this file.

    [pytype]

    # Space-separated list of files or directories to process.
    inputs =
        foo

    # Python version (major.minor) of the target code.
    python_version = 3.6

    # Paths to source code directories, separated by ':'.
    pythonpath =
        .:
        ~/repo2

    # Comma separated list of error names to ignore.
    disable =
        attribute-error

We could've discovered that ``~/repo2`` needed to be added to the
pythonpath by running pytype's broken dependency checker:

::

    $ pytype --config=~/repo1/pytype.cfg ~/repo1/foo/*.py --unresolved

    Unresolved dependencies:
      bar.dependency

Subtools
~~~~~~~~

Pytype ships with three scripts in addition to ``pytype`` itself:

-  ```merge-pyi`` <https://github.com/google/pytype/tree/master/pytype/tools/merge_pyi>`__,
   for merging type information from a .pyi file into a Python file.
-  ``pytd``, a parser for .pyi files.
-  ``pytype-single``, a debugging tool for pytype developers, which
   analyzes a single Python file assuming that .pyi files have already
   been generated for all of its dependencies.

Roadmap
-------

-  Windows support

License
-------

Apache 2.0

Disclaimer
----------

This is not an official Google product.

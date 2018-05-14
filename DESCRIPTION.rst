Pytype
------

Pytype is a static analyzer for Python code.

License
-------

Apache 2.0

Abstract
--------

pytype can statically analyze your Python code, and point out bugs and
errors it finds. It works on any kind of code, and doesn't need any
special directives to be useful.

However, it can additionally verify (and leverage) `type
annotations <https://www.python.org/dev/peps/pep-0484/>`__.

Source
------

Pytype's sources can be found on github:
https://github.com/google/pytype/


Installation
------------

Install pytype from pip

::

    $ pip install pytype

Usage
-----

NOTE: pytype analyzes a single file. To analyze an entire project, use
the included
`pytype-all <https://github.com/google/pytype/tree/master/pytype/tools/analyze_project>`__
tool.

For more detailed explanations of pytype's error messages, see `this
doc <https://github.com/google/pytype/tree/master/docs/errors.md>`__

::

    Usage: pytype [options] file.py

    Infer/check types in a Python module

    Selected options:
      -h, --help            Show the full list of options
      -C, --check           Don't do type inference. Only check for type errors.
      -o OUTPUT, --output=OUTPUT
                            Output file. Use '-' for stdout.
      -V PYTHON_VERSION, --python_version=PYTHON_VERSION
                            Python version to emulate ("major.minor", e.g. "2.7")

Example
-------

Consider the following code, which uses the type annotation syntax from
`PEP 3107 <https://www.python.org/dev/peps/pep-3107/>`__ and `PEP
484 <https://www.python.org/dev/peps/pep-0484/>`__ to declare the
parameter and return types of the function f:

::

    $ cat t.py

    def f(x: int, y: str = 'default') -> int:
      return "foo"

Note that the code above has a bug: The return type is declared to be an
integer, but the function actually returns a string.

Now check it with pytype:

::

    $ pytype -V 3.6 t.py

    File "t.py", line 2, in f: bad option in return type [bad-return-type]
      Expected: int
      Actually returned: str

Pytype can also infer type annotations if they are not explicitly
provided.

::

    $ cat t.py

    class A(object):
      def __init__(self):
        self.x = 10

    p = A()
    q = p.x

Run pytype in inference mode (using the ``-o`` or ``--output`` option):

::

    $ pytype t.py -o -

    p = ...  # type: A
    q = ...  # type: int

    class A(object):
        x = ...  # type: int

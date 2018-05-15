## Pytype

Pytype is a static analyzer for Python code.

## License
Apache 2.0

## Abstract

pytype can statically analyze your Python code, and point out bugs and errors
it finds. It works on any kind of code, and doesn't need any special directives
to be useful.

However, it can additionally verify (and leverage)
[type annotations](https://www.python.org/dev/peps/pep-0484/).

## Installing

Pytype can run under both Python 2.7 and Python 3.6. It also needs an
interpreter in $PATH for the python version of the code you're analyzing
(Python 2.7 by default).

pytype can be installed via pip:

```
pip install pytype
```

The source code can be [found on github](https://github.com/google/pytype/), and
installed via setup.py (note that pytype's `setup.py` relies on setuptools).

```
git clone https://github.com/google/pytype.git
cd pytype
git submodule init
git submodule update
python setup.py install
```

## Usage

NOTE: pytype analyzes a single file. To analyze an entire project, use the
included
[pytype-all](https://github.com/google/pytype/tree/master/pytype/tools/analyze_project) tool.

For more detailed explanations of pytype's error messages, see [this
doc](https://github.com/google/pytype/tree/master/docs/errors.md)

```
Usage: pytype [options] file.py

Infer/check types in a Python module. pytype's major modes are -C [check] and -o
[infer types and write to a file or to stdout].

Options:
  -h, --help            Show the full list of options
  -C, --check           Don't do type inference. Only check for type errors.
  -M MODULE_NAME, --module-name=MODULE_NAME
                        Name of the module we're analyzing. For __init__.py
                        files the package should be suffixed with '.__init__'.
                        E.g. 'foo.bar.mymodule' and 'foo.bar.__init__'
  -o OUTPUT, --output=OUTPUT
                        Output file, for type inference. Use '-' for stdout.
  -P PYTHONPATH, --pythonpath=PYTHONPATH
                        Directories for reading dependencies - a list of paths
                        separated by ':'. The files must have been generated
                        by running pytype on dependencies of the file(s) being
                        analyzed. That is, if an input .py file has an 'import
                        path.to.foo', and pytype has already been run with
                        'pytype path.to.foo.py -o $OUTDIR/path/to/foo.pyi',
                        then pytype should be invoked with $OUTDIR in
                        --pythonpath.
  -V PYTHON_VERSION, --python_version=PYTHON_VERSION
                        Python version to emulate ("major.minor", e.g. "2.7")
  -Z, --quick           Only do an approximation.
  --show-config         Display all config variables and exit.
```

## Example

Consider the following code, which uses the type annotation syntax from [PEP
3107](https://www.python.org/dev/peps/pep-3107/) and [PEP
484](https://www.python.org/dev/peps/pep-0484/) to declare the parameter and
return types of the function f:

```
$ cat t.py

def f(x: int, y: str = 'default') -> int:
  return "foo"
```

Note that the code above has a bug: The return type is declared to be an integer, but the function actually returns a string.

Now check it with pytype:

```
$ pytype -V 3.6 t.py

File "t.py", line 2, in f: bad option in return type [bad-return-type]
  Expected: int
  Actually returned: str
```

Pytype can also infer type annotations if they are not explicitly provided.

```
$ cat t.py

class A(object):
  def __init__(self):
    self.x = 10

p = A()
q = p.x
```

Run pytype in inference mode (using the `-o` or `--output` option):

```
$ pytype t.py -o -

p = ...  # type: A
q = ...  # type: int

class A(object):
    x = ...  # type: int
```

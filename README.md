## Pytype - https://github.com/google/pytype/

Pytype is a static analyzer for Python code.

## License
Apache 2.0

## Abstract

pytype can statically analyze your Python code, and point out bugs and errors
it finds. It works on any kind of code, and doesn't need any special directives
to be useful.

However, it can additionally verify (and leverage)
[type annotations](https://www.python.org/dev/peps/pep-0484/).

## How to get started

Pytype can run under both Python 2.7 and Python 3.6. It also needs an
interpreter in $PATH for the python version of the code you're analyzing
(Python 2.7 by default).

```
git clone https://github.com/google/pytype.git
cd pytype
git submodule init
git submodule update
pip install pyyaml six
python setup.py install
pytype your_python_code.py
```

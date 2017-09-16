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

You currently need Python 2.7 to *run* pytype. (It can *analyze* Python 3, though)

```
git clone https://github.com/google/pytype.git
cd pytype
git submodule init
git submodule update
python setup.py install
pip install pyyaml
pytype your_python_code.py
```

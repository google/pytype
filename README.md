## Pytype - https://github.com/google/pytype/

Pytype is a static type inferencer for Python code.

## License
Apache 2.0

## Motivation
### Why type inferencing?

With [PEP 484](https://www.python.org/dev/peps/pep-0484/), there's now an
official standard for adding type declarations to Python code. This project
aims to help you annotate your source files and to provide automatic static
type-checking for your code.

## How to get started
```
git clone https://github.com/google/pytype.git
git submodule init
git submodule update
python setup.py install
pip install ply
pytype your_python_code.py
```

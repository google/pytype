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

## Type declaration language

Additional to PEP 484 in-line declarations, types declarations can be specified
in an external file with the extension **"pytd"**. For example if you want to
provide types for **"application.py"**, you define the type inside the file
**"application.pytd"**. Examples of type declarations files can be found in the
**/pytd/tests/** folder.

Here’s an example of a simple type declaration file:
```python
class Logger:
  def log(self, messages: list<str>) -> NoneType raises IOException
```

## How to get started
```
git clone https://github.com/google/pytype.git
python setup.py install
pytype -A -O your_python_code.py
```
## How to contribute to the project

* Check out the issue tracker
* Mailing List: https://groups.google.com/forum/#!forum/pytypedecl-dev
* Send us suggestions
* Fork


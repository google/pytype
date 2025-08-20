# An update on pytype

**TL;DR**: The last supported Python version for Pytype will be 3.12. We are
still very actively interested in the space of Python type checking, but
shifting our investments towards new ideas and different frameworks.

Pytype's development began in 2012 to meet Google developers' demand for
compile-time checking. Pytype started with using type inference and interface
files, and then switched to inline annotations (while retaining the inference
engine) after the acceptance of PEP 484. Later, pytype's team collaborated with
Guido and mypy to create typeshed, a central repository for type annotations.

While pytype has been effective, its bytecode-based design has presented
challenges in implementing new features (e.g. faster adoption of new typing
PEPs) due to bytecode’s inherent instability and propensity to change.
Consequently, we intend to focus our investments on exploring new typing
approaches that are better suited for Google’s Python user base and make
Python 3.12 the last supported version for pytype.

We encourage folks to investigate the mature and excellent alternative solutions
for Python typing going forward. We would like to note that the Python typing
ecosystem is very robust now, offering a wider array of mature solutions (see
[FAQ](https://github.com/google/pytype/issues/1925)).

The creation and development of pytype was a collaborative effort, and we would
like to thank all contributors to pytype, especially the four main contributors:
Rebecca Chen, Martin DeMello, Teddy Sudol, and initial lead Matthias Kramm.
We particularly recognize Rebecca Chen for her decade-long commitment to pytype
and her significant contributions to Python's type system as a long-standing
member of the typing council.

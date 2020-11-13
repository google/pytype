# Type Annotations

<!--ts-->
   * [Type Annotations](#type-annotations)
      * [Introduction](#introduction)
      * [Annotations dictionary](#annotations-dictionary)
      * [Converting variable annotations to types](#converting-variable-annotations-to-types)
         * [Forward references](#forward-references)
         * [Complex annotations](#complex-annotations)
         * [Conversion to abstract types](#conversion-to-abstract-types)
      * [Tracking local operations](#tracking-local-operations)

<!-- Added by: rechen, at: 2020-11-13T11:41-08:00 -->

<!--te-->

## Introduction

In [PEP484](https://www.python.org/dev/peps/pep-0484/), python added syntactic
support for type annotations (also referred to as "type hints"). These are
not enforced or applied by the python interpreter, but are instead intended as a
combination of documentation and assertions that can be checked by third-party
tools like pytype. [This blog
post](http://veekaybee.github.io/2019/07/08/python-type-hints/) is a good quick
overview of how type hints fit into the python ecosystem in general.

A significant difference between annotations and type comments is that
annotations are parsed and compiled by the interpreter, even if they have no
semantic meaning in the runtime code. From pytype's point of view, this means
that we can process them as part of the regular bytecode VM (by contrast,
type comments need a [separate system](directives) to parse and integrate them
into the main code). For example, the following code:

```
class A: pass

x: A
```

compiles to

```
SETUP_ANNOTATIONS

... class A definition ...

LOAD_NAME                0 (A)
STORE_ANNOTATION         1 (x)
```

NOTE: Within a function body, type annotations without an assignment (e.g. `x:
A` versus `x: A = foo()`) do not generate any bytecode, and are therefore not
processed by pytype's bytecode VM.

## Annotations dictionary

Python's `SETUP_ANNOTATIONS` and `STORE_ANNOTATION` opcodes respectively create
and populate an `__annotations__` dict in `locals` (for variables in functions)
or in `__dict__` (for annotated class members). Pytype similarly creates a
corresponding dictionary, `abstract.AnnotationsDict`, which it stores in the
equivalent locals or class member dictionary.

The annotations dict is updated via the `vm._update_annotations_dict()` method,
which is called from two entry points:

* `vm._record_local()` records a type annotation on a local variable. The
  AnnotationsDict is retrieved via `self.current_annotated_locals`, which
  gets the AnnotationsDict for the current frame.

* `vm._apply_annotation()` is called with an explicit AnnotationsDict, which, in
  turn, is either the `current_annotated_locals` or the annotations dict for a
  class object, retrieved via
  ```
  annotations_dict = abstract_utils.get_annotations_dict(cls.members)
  ```

A class's AnnotationsDict is also updated directly in `byte_STORE_ATTRIBUTE`,
handling the case where we have an annotation on an attribute assignment that
has not already been recorded as a class-level attribute annotation.


## Converting variable annotations to types

As a first step, type annotations on a variable are converted to pytype's
abstract types, and then stored as the type of that variable in much the same
way assignments are.  Specifically, `x = Foo()` and `x: Foo` should both lead to
the same internal type being retrieved for `x` when it is referred to later in
the code.

### Forward references

Python currently supports two kinds of annotation,

```
x: Foo
```

where `Foo` is treated as a symbol that is looked up in the current namespace,
and then stored under `x` in the `__annotations__` dictionary, and

```
x: 'Foo'
```

where `Foo` is simply stored as a string. The latter case is useful because it
lets us annotate variables with types that have not been defined yet;
annotations of this type are variously referred to as "string annotations",
"forward references" or "late annotations".

### Complex annotations

While an annotation like `x: Foo` corresponds directly to the runtime type
`class Foo`, in general the type annotation system supports more complex types
that do not correspond directly to a runtime python type.

Some examples:

* Parametrised types, e.g. `List[int]` is the type of lists of integers, and
  `Dict[K, V]` is the (generic) type of dictionaries whose keys and values have
  types K and V respectively.
* Union types, e.g. `Union[int, str]` is the type of variables that could
  contain either an `int` or a `str` for the purposes of static type analysis.
  At runtime, they will contain a single concrete type.
* Optional types are a special subcase of unions; `Optional[T] = Union[T,
  None]`.

NOTE: Technically, these types *do* correspond to runtime classes defined in
[typing.py](https://github.com/python/typing/blob/master/src/typing.py), but
that is just an implementation detail to avoid compiler errors when using them.
They are meant to be used by type checkers, not by python code.

Python's general syntax for complex annotations is

```
Base[param1, param2, ...]
```

where the base type `Base` is a python class subclassing `typing.Generic`, and
the `param`s are types (possibly parametrised themselves) or lists of types.

### Conversion to abstract types

The main annotation processing code lives in the
`annotations_util.AnnotationsUtil` class (instantiated as a member of the VM).
This code has several entry points, for various annotation contexts, but the
bulk of the conversion work is done in the internal method
`_process_one_annotation()`.

Unprocessed annotations are represented as `abstract.AnnotationClass` (including the
derived class `abstract.AnnotationContainer`) for immediate annotations, and
`abstract.LateAnnotation` for late annotations. There is also a mixin class,
`mixin.NestedAnnotation`, which has some common code for dealing with inner
types (the types within the `[]` that the base type is parametrised on).

NOTE: The two types can be mixed; an immediate annotation can be parametrised
with a late annotation, e.g. ` x: List['A']` which will eventually be converted
to `x = List[A]` when we can resolve the name `'A'`.

`_process_one_annotation()` is essentially a large switch statement dealing with
various kinds of annotations, and calling itself recursively to deal with nested
annotations. The return value of `_process_one_annotation` is an
`abstract.*` object that can be applied as the python type of a variable.

The various public methods in `AnnotationsUtil` cover different contexts in
which we can encounter variable annotations while processing bytecode; search
for `self.annotations_util` in `vm.py` to see where each one is used.

## Tracking local operations

There is a class of python code that does read type annotations at runtime, for
metaprogramming reasons. The commonest example is `dataclasses` in the standard
library (from python 3.7 onwards); for example the following will generate a
class with an appropriate `__init__` function:

```
@dataclasses.dataclass
class A:
  x: int
  y: str
```

Pytype has some custom [overlay](overlays) code to replicate the effects of
this metaprogramming, but it needs a explicit record of variable annotations,
possibly in the order in which they appear in the code, to handle the general
case. This is distinct from the regular use of annotations to assign types to
variables, and the information we need is not preserved by the regular pytype
type tracking machinery.

To support this use case, we have a separate record of all assignments and
annotations to local variables, stored in a `vm.local_ops` dictionary and
indexed by the current frame. See `vm._record_local()` for how this dictionary
is updated, and `get_class_locals()` in  `overlays/classgen.py` for an instance
of it is used along with `vm.annotated_locals` to recover a class's variable
annotations.

[directives]: directives.md
[overlays]: overlays.md

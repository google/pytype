# Special Builtins

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-09-18' }
*-->

<!--ts-->
   * [Special Builtins](#special-builtins)
      * [Overview](#overview)
      * [Representation](#representation)
      * [Invoking](#invoking)
      * [Implementation details](#implementation-details)
         * [Method delegation](#method-delegation)
         * [Slots](#slots)
         * [Instances](#instances)
      * [Variables and data](#variables-and-data)

<!-- Added by: mdemello, at: 2020-09-21T13:57-07:00 -->

<!--te-->

## Overview

As discussed elsewhere, pytype's primary model for function and method calls is
the function signature. A function is modelled as

```
def f(arg1: type1, ...) -> return_type:
  mutated_arg = new_type
  ...
```

and when the pytype VM calls the function, it matches the argument types against
the types of the passed-in variables, performs any type mutations, and pushes a
return type onto the stack.

Since the VM deals with types rather than values, we typically do not care
about any side effects a function may have (other than the aforementioned type
mutations). However, there are some functions that either have complex
type-level side effects (e.g. adding class attributes via metaprogramming) or
have type effects that depend on the *values* of the arguments. Type matching
and unification are insufficient to cover this; we need to directly manipulate
the abstract values we use to represent python objects.

There are two main sections of the pytype codebase dealing with these functions
- **special builtins**, which handle functions like `super()` that are part of
the python core language, and **overlays**, which handle both standard and
third-party libraries.

NOTE: These special functions still need type signatures to interoperate with
the rest of pytype; in the case of `special_builtins.py` the corresponding
signatures can be found in `__builtin__.pytd`

## Representation

`special_builtins.py` defines two classes, `BuiltinFunction` and `BuiltinClass`,
which all special builtins inherit from. These are subclasses of
`abstract.PyTDFunction` and `abstract.PyTDClass` respectively.

The main use case for these builtins is to override the `call` method, following
python's implementation of them as callable functions/classes. For example,
`next(x)` compiles to

```
LOAD_GLOBAL              0 (next)
LOAD_FAST                0 (x)
CALL_FUNCTION            1
```

that is, it loads `next` as a global object and calls its `call` method. When
pytype analyses this bytecode it needs to implement any special behaviour when
`next` is called, not when it is loaded.

The return types of special builtins are sometimes special objects too; we model
these with corresponding custom classes deriving directly from
`abstract.AtomicAbstractValue` and implementing the right behaviour for various
attribute and method accesses.

## Invoking

`VirtualMachine.__init__` defines a mapping `self.special_builtins` from the
names of python builtins to instances of the corresponding special builtins.
Each special builtin then provides its own implementation of `call`, and when
the VM encounters a call to e.g. `next(arg)` it delegates to
`special_builtins.Next().call(arg)`.

The VM loads python builtins by calling `load_builtin()` in `byte_LOAD_NAME`.
`load_builtin()` in turn calls `load_special_builtin()` to check if the name we
are loading is defined in the `self.special_builtins` mapping mentioned above.

## Implementation details

While each special builtin is ultimately custom code mirroring the details of
the corresponding python builtin, there are some common techniques that all the
implementations use.

### Method delegation

A lot of special functions delegate to a method call on their first argument,
e.g. `abs(x)` calls `x.__abs__()` internally. The base `BuiltinFunction` class
provides a `get_underlying_method` helper for subclasses to use; e.g. `Abs.call`
calls

```
self.get_underlying_method(node, arg, "__abs__")
```

and then just reinvokes the regular `vm.call_function()` but now calling the
bound method `x.__abs__` rather than the built in function `abs` (this is a good
example of something that is fairly straightforward but nevertheless impossible
to do via type signatures).

### Slots

Slots are a [python
mechanism](https://docs.python.org/3/reference/datamodel.html#slots) by which a
class can provide a single `__slots__` dictionary for attribute lookup, rather
than a per-instance `__dict__`. Pytype uses an analogous mechanism internally by
which a class can provide slots to support custom method overrides.

Special builtins that need to override methods other than `call` mix in
`mixin.HasSlots` and provide a list of slots and an overridden implementation
for each one. As with `call` these implementations need to do something more
complex than the default of matching a signature and providing the correct
return type.

For example, `special_builtins.PropertyInstance` binds the `__get__` method of
the property to a decorated method in the target code by setting a slot:

```
class PropertyInstance(mixin.HasSlots, ...):
  def __init__(self, fget, ...):
    # sets the InterpreterFunction to call
    self.fget = fget
    # will be invoked when the target bytecode calls the property
    self.set_slot("__get__", self.fget_slot)

  def fget_slot(self, ...):
    return self.vm.call_function(self.fget, ...)
```

NOTE: Slots are implemented via the `get_special_attribute` method in
the `abstract.py/AtomicAbstractValue` hierarchy and the corresponding override
in `mixin.HasSlots`.

### Instances

As mentioned earlier, calling `some_builtin.call()` often returns another
special object. This is typically the case for a builtin exhibiting multi-stage
behaviour (e.g. a method decorator has two relevant invocation points, first
wrapping a method and returning a new method, and then performing some custom
behaviour when the wrapped method is called).

We will take a look at the implementation of `@staticmethod` as an example.

```
class A:
  @staticmethod
  def f(cls):
    pass
```

compiles to

```
LOAD_NAME                3 (staticmethod)
LOAD_CONST               1 (<code object f>)
LOAD_CONST               2 ('A.f')
MAKE_FUNCTION            0
CALL_FUNCTION            1
STORE_NAME               4 (f)
```

i.e. it loads `staticmethod`, loads the code object for `f`, calls
`staticmethod(f)` and stores the return value as `f` again; this is our wrapped
staticmethod. Calling `A.f()` will now find the wrapped method; i.e. we have (at
runtime!) taken the instance method `A().f` and moved it into the static method
`A.f`.

Pytype replicates this behaviour by providing a `StaticMethod` class, whose
`call` method takes in a function (specifically a variable whose binding is an
`abstract.InterpreterFunction` object), and returns a `StaticMethodInstance`
that wraps the original variable. `StaticMethodInstance` in turn wraps the
underlying function and provides an object whose `get_class()` method returns
`special_builtins.StaticMethod` and whose `__get__` slot returns the original
function. (The details of `StaticMethodInstance` don't matter too much for now,
but note the two-stage process by which we have achieved the desired method
overrides on the `f` object.)

## Variables and data

As a side note, when reading the `special_builtins` code it is essential to keep
clear the distinction between Data (representation of python objects) and
Variables (typegraph representations of a python variable, potentially with
multiple Bindings to data). The special builtins' `call()` methods all take
arguments in `Variable` form, perform computations on the underlying
`AtomicAbstractValue`s, and then construct a new `Variable` with the results of
those computations.

Look for the pattern

```
def call(*args):
  result = self.vm.program.NewVariable()

  # unpack data from args
  ...

  # special builtin code here
  ...

  # update result variable
  result.AddBinding(some_data)
  # and/or
  result.PasteVariable(some_variable)

  return node, result
```

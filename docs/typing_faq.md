# Pytype's Type System

<!--*
freshness: { owner: 'mdemello' reviewed: '2021-07-27' }
*-->

<!--ts-->
   * [Pytype's Type System](#pytypes-type-system)
      * [Why do pytype's semantics differ from mypy's?](#why-do-pytypes-semantics-differ-from-mypys)
      * [Why does pytype allow adding multiple types to a container?](#why-does-pytype-allow-adding-multiple-types-to-a-container)
      * [Why is Optional[Optional[T]] the same as Optional[T]?](#why-is-optionaloptionalt-the-same-as-optionalt)
      * [Why is pytype not more like $other_language?](#why-is-pytype-not-more-like-other_language)

<!-- Added by: rechen, at: 2021-08-05T17:23-07:00 -->

<!--te-->

## Why do pytype's semantics differ from mypy's?

This FAQ refers to "pytype" rather than "python" because typing semantics in the
python world are a property of the type checker rather than of the language.
There are several python type checkers, and while they do aim for consistency
with the relevant PEPs, they do not behave identically. See, for instance, [this
paper][type-system-paper] detailing pytype and mypy's differing views of
python's type system.

As the primary open source type checker, [mypy] tends to de facto define the
semantics of what people think of as "python typing" in areas not formally
covered by a PEP. Pytype does try to be consistent with mypy, and with other
type checkers like pyre and pyright; not counting bugs the primary source of
differences is the desire to not break existing, unannotated code that follows
valid python idioms.

## Why does pytype allow adding multiple types to a container?

One somewhat surprising behaviour is illustrated by the following snippet:

```python
xs = [1, 2, 3]
reveal_type(xs)  # => List[int]
xs.append('hello')  # no error!
reveal_type(xs)  # => List[Union[int, str]]
```

Given that `xs` is correctly inferred as `List[int]` in line 2, it could be
expected that adding a string to it would be a type error. However, this is
perfectly valid python code, and in this case pytype chooses to be descriptive
rather than prescriptive, modifying the type of `xs` to match the actual
contents.

Explicitly annotating xs with a type will indeed raise a
`container-type-mismatch` error:

```python
xs: List[int] = [1, 2, 3]
xs.append('hello')  # ! container-type-mismatch
```

## Why is Optional[Optional[T]] the same as Optional[T]?

Consider the following code:

```python
x: Dict[str, Optional[str]] = {'a': 'hello', 'b': None}
a = x.get('a')
b = x.get('b')
c = x.get('c')
```

Since the signature of `dict.get` is

```python
class Mapping(Generic[K, V]):
  def get(key: K) -> Optional[V]
```

an ML-based language would indeed have a return type of
`Optional[Optional[str]]`, and be able to distinguish a value of `None` from a
missing value. This comes down to the fact that python has union rather than sum
types; `Optional[T]` is an alias for `Union[T, None]`, and therefore, by a
series of expansions,

```python
Optional[Optional[T]]
= Union[Union[T, None], None]
= Union[T, None, None]
= Union[T, None]
= Optional[T]
```

Note that this is simply a difference of behaviour, not a flaw in either python
or pytype; in particular `Optional` being a sum type would mean `Optional[T]`
was an alias for `None | Some[T]` rather than `None | T`, which would mean every
dictionary key access would need to be unwrapped before being used.

## Why is pytype not more like $other\_language?

We often get questions about why pytype's typing semantics differ from
C++/Java/ML/Haskell/etc. -- common issues include containers being heterogeneous,
and `Union`s being untagged ("union types" as opposed to "sum types"). The
primary reason is that all those languages are statically typed; python is
dynamically typed, and type checkers like pytype add [gradual typing][gradual]
on top of that. While gradual typing may resemble static typing, it has a very
different foundation and emphasis, which is to augment a dynamic language with
optional types.

When discussing pytype's design and limitations, it is important to distinguish
type-theoretical properties like soundness and completeness ([this is a good
overview][overview]) from the expectation of static typing behaviour in a
gradually typed language. It is more useful to compare pytype to other gradually
typed languages like [TypeScript][typescript] (adding gradual types to
JavaScript), [Typed Racket][racket] (adding gradual types to Racket) and
[Stanza][stanza] (designed with a gradual type system), and look at python
typing in the light of some of the decisions those other languages made.

Note that gradual typing is not a poor approximation to static typing, it simply
makes a different set of tradeoffs between type safety, expressiveness,
ergonomics and performance. And within the realm of gradual typing (an active
area of research) different languages select different tradeoffs; for instance
typed racket does emphasise soundness, but requires more explicit boundaries
between typed and untyped code, and run-time contracts to enforce some
invariants.

Stanza's author [explains][stanza-typing] the rationale behind union types, for
instance:

> We have found union types to be an absolute necessity for being able to add
> types to untyped code without necessitating a structural change.

> As an interesting aside, proper support for untagged union types also allows
> Stanza to omit the concept of a null value. A common idiom that is used to
> indicate that a variable may be "uninitialized" is to assign it the value
> false. Thus a variable holding a possibly uninitialized integer could be
> declared with type
>
> `var x: Int|False = false`
>
> indicating that x might have the value false, and any usages of x as an Int
> must first be checked. This elegantly sidesteps what Hoare called his
> "billion-dollar mistake", and Stanza has no analogue to Java's notorious
> NullPointerException.

and the [TypeScript documentation][typescript-typing] has an explicit note on
soundness:

> TypeScript’s type system allows certain operations that can’t be known at
> compile-time to be safe. When a type system has this property, it is said to
> not be “sound”. The places where TypeScript allows unsound behavior were
> carefully considered, and throughout this document we’ll explain where these
> happen and the motivating scenarios behind them.

Some other interesting writing on the topic:

- [Typing is hard][hard]
- [Are unsound typed systems wrong?][unsound]
- [Safety and soundness][safety]
- [A spectrum of type soundness and performance][performance]
- [Is sound gradual typing dead][soundness]

[hard]: https://3fx.ch/typing-is-hard.html
[gradual]: https://blog.sigplan.org/2019/07/12/gradual-typing-theory-practice/
[mypy]: http://mypy-lang.org/
[overview]: http://logan.tw/posts/2014/11/12/soundness-and-completeness-of-the-type-system/
[performance]: http://prl.ccs.neu.edu/blog/2018/10/06/a-spectrum-of-type-soundness-and-performance/
[racket]: https://docs.racket-lang.org/ts-guide/types.html
[safety]: https://papl.cs.brown.edu/2014/safety-soundness.html
[soundness]: https://www2.ccs.neu.edu/racket/pubs/popl16-tfgnvf.pdf
[stanza]: http://lbstanza.org/index.html
[stanza-typing]: http://lbstanza.org/optional_typing.html
[typescript]: https://www.typescriptlang.org/
[typescript-typing]: https://www.typescriptlang.org/docs/handbook/type-compatibility.html
[type-system-paper]: https://www.cs.rpi.edu/~milanova/docs/dls2020.pdf
[unsound]: https://frenchy64.github.io/2018/04/07/unsoundness-in-untyped-types.html

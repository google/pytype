<!--* freshness: { exempt: true } *-->

# Support

This page lists the Python versions and features supported by the latest version
of pytype.

<!--ts-->
* [Support](#support)
   * [Python Version](#python-version)
   * [Features](#features)
      * [Core](#core)
      * [Typing](#typing)
      * [Non-Standard {#non_standard_features}](#non-standard-non_standard_features)
      * [Experimental {#experiments}](#experimental-experiments)
         * [Ellipsis Annotation {#experimental_pytype_ellipsis_annotation}](#ellipsis-annotation-experimental_pytype_ellipsis_annotation)
      * [Third-Party Libraries](#third-party-libraries)

<!-- Created by https://github.com/ekalinin/github-markdown-toc -->
<!-- Added by: rechen, at: Mon Dec 18 11:42:58 AM PST 2023 -->

<!--te-->

## Python Version

*   **Analyzes**: Whether pytype can analyze code written for this version. For
    deprecated versions, the last pytype release that supports this version.
*   **Runs In**: Whether pytype itself can run in this version. For deprecated
    versions, the last pytype release that supports this version.
*   **Issue**: Tracking issue for dropping support (older versions) or adding it
    (upcoming versions), if applicable

Version | Analyzes   | Runs In    | Issue
:-----: | :--------: | :--------: | :----------:
2.7     | 2021.08.03 | 2020.04.01 | [#545][py27]
3.5     | 2021.09.09 | 2020.10.08 | [#677][py35]
3.6     | 2022.01.05 | 2022.01.05 |
3.7     | 2023.06.16 | 2023.06.16 |
3.8     | ✅          | ✅          |
3.9     | ✅          | ✅          |
3.10    | ✅          | ✅          |
3.11    | ✅          | ✅          |
3.12    | ❌          | ❌          |

## Features

*   **Supports**: ✅ (yes), ❌ (no), or 🟡 (partial)
*   **Issues**: Notable issue(s), if applicable

### Core

Note: pytype supports all language and stdlib features in its supported versions
unless noted otherwise. This section lists features that are difficult to type
for which pytype has or intends to add custom support.

Feature                                  | Supports | Issues
---------------------------------------- | :------: | :----:
Control Flow Analysis ("Type Narrowing") | ✅        |
collections.namedtuple                   | ✅        |
Dataclasses                              | ✅        |
Enums                                    | ✅        |

### Typing

Feature                                                                                 | Version | Supports | Issues
--------------------------------------------------------------------------------------- | :-----: | :------: | :----:
[PEP 484 -- Type Hints][484]                                                            | 3.5     | ✅        |
[PEP 526 -- Syntax for Variable Annotations][526]                                       | 3.6     | ✅        |
[PEP 561 -- Distributing and Packaging Type Information][561]                           | 3.7     | ❌        | [#151][packaging]
[PEP 563 -- Postponed Evaluation of Annotations][563]                                   | 3.7     | ✅        |
[PEP 544 -- Protocols][544]                                                             | 3.8     | ✅        |
[PEP 586 -- Literal Types][586]                                                         | 3.8     | ✅        |
[PEP 589 -- TypedDict][589]                                                             | 3.8     | ✅        |
[PEP 591 -- Adding a Final Qualifier to Typing][591]                                    | 3.8     | ✅        |
[PEP 585 -- Type Hinting Generics in Standard Collections][585]                         | 3.9     | ✅        |
[PEP 593 -- Flexible Function and Variable Annotations][593]                            | 3.9     | ✅        |
[PEP 604 -- Allow Writing Union Types as X \| Y][604]                                   | 3.10    | ✅        |
[PEP 612 -- Parameter Specification Variables][612]                                     | 3.10    | 🟡        | [#786][param-spec]
[PEP 613 -- Explicit Type Aliases][613]                                                 | 3.10    | ✅        |
[PEP 647 -- User-Defined Type Guards][647]                                              | 3.10    | ✅        |
[PEP 646 -- Variadic Generics][646]                                                     | 3.11    | ❌        | [#1525][variadic-generics]
[PEP 655 -- Marking individual TypedDict items as required or potentially-missing][655] | 3.11    | ❌        | [#1551][typed-dict-requirements]
[PEP 673 -- Self Type][673]                                                             | 3.11    | ✅        |
[PEP 675 -- Arbitrary Literal String Type][675]                                         | 3.11    | ❌        | [#1552][literal-string]
[PEP 681 -- Data Class Transforms][681]                                                 | 3.11    | 🟡        | [#1553][dataclass-transform]
[PEP 695 -- Type Parameter Syntax][695]                                                 | 3.12    | ❌        |
[PEP 698 -- Override Decorator for Static Typing][698]                                  | 3.12    | ✅        |
Custom Recursive Types                                                                  | 3.6     | ✅        |
Generic Type Aliases                                                                    | 3.6     | ✅        |
Type Annotation Inheritance                                                             | 3.6     | ❌        | [#81][annotation-inheritance]

### Non-Standard {#non_standard_features}

This section describes notable non-standard features supported by pytype.

Note: This is not and does not endeavor to be an exhaustive list of the ways in
which pytype differs from other Python type checkers. See the
[Pytype Typing FAQ][pytype-typing-faq] for more on that topic.

*   Pytype forbids `str` from matching an iterable of `str`s, in order to catch
    a common accidental string iteration bug
    ([FAQ entry][faq-noniterable-strings]).
*   `pytype_extensions`: The `pytype_extensions` namespace contains many useful
    extensions, mostly user-contributed. The best way to learn about them is to
    read the [inline documentation][pytype-extensions].
*   Pytype allows type-annotated variables to be assigned to `None` or `...`
    without including the relevant type in the type annotation. For example, `x:
    str = None` and `x: str = ...` are allowed. This makes it easier to
    type-annotate code that uses `None` or `...` to indicate an unset value.

### Experimental {#experiments}

This section describes short-lived experimental features that pytype is trialing
which aren't part of the typing spec. In general, experiments are confined to
the non-opensourced parts of the Google codebase since they are not supported by
other type-checking systems.

By default, experiments have a maximum lifetime of 24 months. They will then
either be incorporated into a widely accepted, non-Google only standard or
reverted. In either case, our team will be responsible for any remaining code
cleanups. The lifetime of an experiment may be extended if forward progress
toward adoption by the wider typing community is shown.

#### Ellipsis Annotation {#experimental_pytype_ellipsis_annotation}

*   Start date: [Jan 2022][experimental-ellipsis-commit]
*   End date: 2024
*   Reference: [feature request and discussion][ellipsis-issue]
*   Details: Pytype allows `...` as a top-level annotation. When used this way,
    `...` means "inferred type".

    For example, when you use `...` as the annotation for a function's return
    type, the type will be inferred from the function body:

    ```python
    def f() -> ...:  # return type inferred as `int`
      return 0
    ```

    For a variable annotation, the type will be inferred from the assignment:

    ```python
    _X: ... = 0  # type of `_X` inferred as `int`
    ```

    Note: pytype does not guarantee any particular inference strategy. Types
    annotated as `...` may even be inferred as `Any`, effectively locally
    disabling type analysis.

    Warning: using `...` as a top-level annotation is an experimental feature
    that is supported only by pytype. Do not use it on any code that is
    opensourced. Other type checkers such as mypy, pyright, and pycharm will
    consider this annotation to be an error since it is an experiment and is not
    part of the current language standard.

### Third-Party Libraries

Note: This section does not list all third-party libraries that pytype supports,
only the ones that are difficult to type for which pytype has or intends to add
custom support.

Feature    | Supports | Issues
---------- | :------: | :----------------------:
Attrs      | ✅        |
Chex       | 🟡        | Google-internal
Flax       | 🟡        | Google-internal
Numpy      | 🟡        | Minimal type stub
Tensorflow | 🟡        | Minimal, Google-internal

[484]: https://www.python.org/dev/peps/pep-0484
[526]: https://www.python.org/dev/peps/pep-0526
[544]: https://www.python.org/dev/peps/pep-0544
[561]: https://www.python.org/dev/peps/pep-0561
[563]: https://www.python.org/dev/peps/pep-0563
[585]: https://www.python.org/dev/peps/pep-0585
[586]: https://www.python.org/dev/peps/pep-0586
[589]: https://www.python.org/dev/peps/pep-0589
[591]: https://www.python.org/dev/peps/pep-0591
[593]: https://www.python.org/dev/peps/pep-0593
[604]: https://www.python.org/dev/peps/pep-0604
[612]: https://www.python.org/dev/peps/pep-0612
[613]: https://www.python.org/dev/peps/pep-0613
[646]: https://www.python.org/dev/peps/pep-0646
[647]: https://www.python.org/dev/peps/pep-0647
[655]: https://peps.python.org/pep-0655/
[673]: https://www.python.org/dev/peps/pep-0673
[675]: https://peps.python.org/pep-0675/
[681]: https://peps.python.org/pep-0681/
[695]: https://peps.python.org/pep-0695/
[698]: https://peps.python.org/pep-0698/
[annotated]: https://github.com/google/pytype/issues/791
[annotation-inheritance]: https://github.com/google/pytype/issues/81
[dataclass-transform]: https://github.com/google/pytype/issues/1553
[ellipsis-issue]: https://github.com/python/typing/issues/276
[experimental-ellipsis-commit]: https://github.com/google/pytype/commit/9f3f21e7a5bcedf6584bb41fd228878498182991
[faq-noniterable-strings]: https://google.github.io/pytype/faq.html#why-doesnt-str-match-against-string-iterables
[generic-aliases]: https://github.com/google/pytype/issues/793
[literal-string]: https://github.com/google/pytype/issues/1552
[packaging]: https://github.com/google/pytype/issues/151
[param-spec]: https://github.com/google/pytype/issues/786
[py27]: https://github.com/google/pytype/issues/545
[py35]: https://github.com/google/pytype/issues/677
[py311]: https://github.com/google/pytype/issues/1308
[pytype-extensions]: https://github.com/google/pytype/tree/main/pytype_extensions/__init__.py
[pytype-typing-faq]: https://google.github.io/pytype/typing_faq.html
[self]: https://github.com/google/pytype/issues/1283
[type-guards]: https://github.com/google/pytype/issues/916
[typed-dict-requirements]: https://github.com/google/pytype/issues/1551
[variadic-generics]: https://github.com/google/pytype/issues/1525

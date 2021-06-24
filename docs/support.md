# Support

<!--* freshness: { owner: 'rechen' reviewed: '2021-01-08' } *-->

This page lists the Python versions and features supported by the latest version
of pytype.

<!--ts-->
   * [Support](#support)
      * [Python Version](#python-version)
      * [Features](#features)
         * [Core](#core)
         * [Typing](#typing)
         * [Third-Party Libraries](#third-party-libraries)

<!-- Added by: rechen, at: 2021-06-24T11:18-07:00 -->

<!--te-->

## Python Version

*   **Analyzes**: Whether pytype can analyze code written for this version
*   **Runs In**: Whether pytype itself can run in this version
*   **Issue**: Tracking issue for dropping support (older versions) or adding it
    (upcoming versions), if applicable

Version | Analyzes | Runs In | Issue
:-----: | :------: | :-----: | :----------:
2.7     | ✅        | ❌       | [#545][py27]
3.5     | ✅        | ❌       | [#677][py35]
3.6     | ✅        | ✅       |
3.7     | ✅        | ✅       |
3.8     | ✅        | ✅       |
3.9     | ✅        | ✅       |
3.10    | ❌        | ❌       |

## Features

*   **Supports**: ✅ (yes), ❌ (no), or 🟡 (partial)
*   **Issues**: Notable issue(s), if applicable

### Core

Note: pytype supports all language and stdlib features in its supported versions
unless noted otherwise. This section lists features that are difficult to type
for which pytype has or intends to add custom support.

Feature                                  | Supports | Issues
---------------------------------------- | :------: | :----------:
Control Flow Analysis ("Type Narrowing") | ✅        |
collections.namedtuple                   | ✅        |
Dataclasses                              | ✅        |
Enums                                    | 🟡        | [#788][enum]

### Typing

Feature                                                         | Supports | Issues
--------------------------------------------------------------- | :------: | :----:
[PEP 484 -- Type Hints][484]                                    | ✅        |
[PEP 526 -- Syntax for Variable Annotations][526]               | ✅        |
[PEP 544 -- Protocols][544]                                     | 🟡        | [#789][protocol-modules]
[PEP 561 -- Distributing and Packaging Type Information][561]   | ❌        | [#151][packaging]
[PEP 563 -- Postponed Evaluation of Annotations][563]           | ✅        |
[PEP 585 -- Type Hinting Generics in Standard Collections][585] | ✅        |
[PEP 586 -- Literal Types][586]                                 | 🟡        | [#790][literal-enums]
[PEP 589 -- TypedDict][589]                                     | ❌        | [#680][typeddict]
[PEP 591 -- Adding a Final Qualifier to Typing][591]            | ❌        | [#680][final]
[PEP 593 -- Flexible Function and Variable Annotations][593]    | ✅        |
[PEP 604 -- Allow Writing Union Types as X \| Y][604]           | ❌        | [#785][union-pipe]
[PEP 612 -- Parameter Specification Variables][612]             | ❌        | [#786][param-spec]
[PEP 613 -- Explicit Type Aliases][613]                         | ❌        | [#787][typealias]
[PEP 647 -- User-Defined Type Guards][647]                      | ❌        | [#916][type-guards]
Custom Recursive Types                                          | ❌        | [#407][recursive-types]
Generic Type Aliases                                            | ✅        | Requires `--preserve-union-macros` flag
Type Annotation Inheritance                                     | ❌        | [#81][annotation-inheritance]

### Third-Party Libraries

Note: This section does not list all third-party libraries that pytype supports,
only the ones that are difficult to type for which pytype has or intends to add
custom support.

Feature    | Supports | Issues
---------- | :------: | :----------------------:
Attrs      | ✅        |
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
[647]: https://www.python.org/dev/peps/pep-0647
[annotated]: https://github.com/google/pytype/issues/791
[annotation-inheritance]: https://github.com/google/pytype/issues/81
[enum]: https://github.com/google/pytype/issues/788
[final]: https://github.com/google/pytype/issues/680
[generic-aliases]: https://github.com/google/pytype/issues/793
[literal-enums]: https://github.com/google/pytype/issues/790
[packaging]: https://github.com/google/pytype/issues/151
[param-spec]: https://github.com/google/pytype/issues/786
[protocol-modules]: https://github.com/google/pytype/issues/789
[py27]: https://github.com/google/pytype/issues/545
[py35]: https://github.com/google/pytype/issues/677
[py39]: https://github.com/google/pytype/issues/749
[recursive-types]: https://github.com/google/pytype/issues/407
[type-guards]: https://github.com/google/pytype/issues/916
[typealias]: https://github.com/google/pytype/issues/787
[typeddict]: https://github.com/google/pytype/issues/680
[union-pipe]: https://github.com/google/pytype/issues/785

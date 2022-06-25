# Support

<!--* freshness: { owner: 'rechen' reviewed: '2022-01-12' } *-->

This page lists the Python versions and features supported by the latest version
of pytype.

<!--ts-->
   * [Support](#support)
      * [Python Version](#python-version)
      * [Features](#features)
         * [Core](#core)
         * [Typing](#typing)
         * [Third-Party Libraries](#third-party-libraries)

<!-- Added by: rechen, at: 2022-06-22T23:51-07:00 -->

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
3.7     | ✅          | ✅          |
3.8     | ✅          | ✅          |
3.9     | ✅          | ✅          |
3.10    | ✅          | ✅          |
3.11    | ❌          | ❌          |

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
Enums                                    | ✅        | Requires `--use-enum-overlay` flag externally

### Typing

Feature                                                                                 | Version | Supports | Issues
--------------------------------------------------------------------------------------- | :-----: | :------: | :----:
[PEP 484 -- Type Hints][484]                                                            | 3.5     | ✅        |
[PEP 526 -- Syntax for Variable Annotations][526]                                       | 3.6     | ✅        |
[PEP 544 -- Protocols][544]                                                             | 3.8     | ✅        |
[PEP 561 -- Distributing and Packaging Type Information][561]                           | 3.7     | ❌        | [#151][packaging]
[PEP 563 -- Postponed Evaluation of Annotations][563]                                   | 3.7     | ✅        |
[PEP 585 -- Type Hinting Generics in Standard Collections][585]                         | 3.9     | ✅        |
[PEP 586 -- Literal Types][586]                                                         | 3.8     | ✅        |
[PEP 589 -- TypedDict][589]                                                             | 3.8     | ✅        |
[PEP 591 -- Adding a Final Qualifier to Typing][591]                                    | 3.8     | ✅        |
[PEP 593 -- Flexible Function and Variable Annotations][593]                            | 3.9     | ✅        |
[PEP 604 -- Allow Writing Union Types as X \| Y][604]                                   | 3.10    | ✅        |
[PEP 612 -- Parameter Specification Variables][612]                                     | 3.10    | ❌        | [#786][param-spec]
[PEP 613 -- Explicit Type Aliases][613]                                                 | 3.10    | ✅        |
[PEP 646 -- Variadic Generics][646]                                                     | 3.11    | ❌        |
[PEP 647 -- User-Defined Type Guards][647]                                              | 3.10    | ❌        | [#916][type-guards]
[PEP 655 -- Marking individual TypedDict items as required or potentially-missing][655] | 3.11    | ❌        |
[PEP 673 -- Self Type][673]                                                             | 3.11    | ❌        |
[PEP 675 -- Arbitrary Literal String Type][675]                                         | 3.11    | ❌        |
[PEP 681 -- Data Class Transforms][681]                                                 | 3.11    | ❌        |
Custom Recursive Types                                                                  | 3.6     | ✅        |
Generic Type Aliases                                                                    | 3.6     | ✅        |
Type Annotation Inheritance                                                             | 3.6     | ❌        | [#81][annotation-inheritance]

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
[annotated]: https://github.com/google/pytype/issues/791
[annotation-inheritance]: https://github.com/google/pytype/issues/81
[generic-aliases]: https://github.com/google/pytype/issues/793
[packaging]: https://github.com/google/pytype/issues/151
[param-spec]: https://github.com/google/pytype/issues/786
[py27]: https://github.com/google/pytype/issues/545
[py35]: https://github.com/google/pytype/issues/677
[py39]: https://github.com/google/pytype/issues/749
[py310]: https://github.com/google/pytype/issues/1022
[type-guards]: https://github.com/google/pytype/issues/916

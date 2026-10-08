# PV-PP Programmer's Reference — code skeletons

These files accompany *PV-PP Programmer's Reference*, Edition 2.1 for **frozen PV-PP Runtime v2.1.167 (Framework 2.1, Build 167)**.

The Reference is the detailed lookup volume for the runtime's types, methods, contracts, statuses, invariants, errors, limits, and supervision surface. The `skeletons/` directory contains the runnable host-code skeletons printed and described in Appendix B.

- `PVPP_Programmers_Reference_Ed2.1_v2.1.167.docx` — editable publication document.
- `PVPP_Programmers_Reference_Ed2.1_v2.1.167.pdf` — publication PDF.
- `skeletons/` — Appendix B runnable skeletons and their tests, including the supervision example.

The skeletons are host code written for the book. They are **not part of the frozen runtime evidence base**.

## Running the skeletons

Requires Python 3.11 or later and pytest.

From the `skeletons/` directory:

```bash
export PVPP_RUNTIME_PATH="<path to this repository>/runtime-v2.1.167"
PYTHONPATH="$PVPP_RUNTIME_PATH:." PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The banked Appendix B skeleton result is **15 passed** against the hash-verified frozen v2.1.167 tree.

The skeleton harness verifies the v2.1.167 runtime identity. It can also check the preserved build-141 manifest to demonstrate that the decision core is unchanged apart from the expected package-metadata difference documented by the Reference.

## Authority and scope

The Reference documents the runtime; it does not redefine it. If this book or these skeletons conflict with the frozen v2.1.167 source, tests, or controlling manifest, the frozen runtime evidence controls.

Runtime v2.1.167 carries forward the build-141 decision core and adds the supervision layer documented in Chapter 16. The canonical decision core remains synchronous. Host instrumentation supplies observations, host code invokes supervision, the runtime governs continuation and control authority, and external controllers perform actual enforcement and world effects.

The frozen runtime's full regression result is **1320/1320 passing**. The Appendix B skeleton tests are separate confirmation code and must not be counted as part of that frozen regression suite.

## License

The Appendix B code skeletons distributed in this repository are licensed under the Apache License, Version 2.0, as stated in the Reference and repository license. The Reference text is licensed under CC BY 4.0 as stated in the book.

PV-PP™ is a trademark of Lance Amundsen.

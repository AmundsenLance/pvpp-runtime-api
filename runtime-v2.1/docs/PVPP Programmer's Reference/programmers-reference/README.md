# PV-PP Programmer's Reference — code skeletons

These files accompany *PV-PP Programmer's Reference*, Edition 2.1. They are exact copies of the six host skeletons
and their test file printed in the book's Appendix B (Listings B.1–B.7).

## Running them

Requires Python 3.11 or later and pytest.

```
R="<path to this repository>/runtime-v2.1"
cd skeletons
PYTHONPATH="$R:." PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider   # expected: 6 passed
PYTHONPATH="$R:." python3 b2_cycle.py
```

The skeletons target PV-PP Runtime V2.1, frozen build v0.141. Verify that build first (book, Section 13.7).
They are host code written for the book, not part of the frozen runtime.
Licensed under the Apache License, Version 2.0, as is the rest of this repository.

PV-PP™ is a trademark of Lance Amundsen.

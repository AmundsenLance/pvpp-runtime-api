# PV-PP Programmer's Guide — programs

These files accompany *PV-PP Programmer's Guide*, Edition 2.1. They are exact copies of the programs listed in the
book's Appendix G; the book prints and explains each one.

- `programs/` — the coffee-vending application (Chapters 6–9) and the operations agent (Chapter 10), with their tests.
  Keep all files in one folder: `coffee_execute.py` imports `coffee_decision.py`, and the Chapter 9 tests import
  `coffee_app.py` and read `coffee_day_expected.txt`.

## Running them

Requires Python 3.11 or later and pytest.

```
export PVPP_RUNTIME_PATH="<path to this repository>/runtime-v2.1"
cd programs
python3 coffee_app.py            # output should match the listing in its chapter
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider   # expected: 43 passed
```

Results are claimed for PV-PP Runtime V2.1, frozen build v0.141, only. Verify that build first (book, Appendix G.3).
Licensed under the Apache License, Version 2.0, as is the rest of this repository.

PV-PP™ is a trademark of Lance Amundsen.

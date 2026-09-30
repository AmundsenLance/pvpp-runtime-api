# PV-PP Getting Started — companion files

These files accompany *PV-PP Getting Started*, Edition 2.1 (DOI 10.5281/zenodo.23071376).
They are exact copies of material printed in the book; the book is complete without them.

- `battery/` — the six tutorial files of Chapter 5 (`step1_registry.py` to `step5_act.py`, `test_battery.py`).
- `ai-rules-and-prompts.txt` — Listings 7.1 to 7.4: the rules and three prompts for AI-assisted development.

## Running the tutorial

Requires Python 3.11 or later and pytest. From this folder:

```
export PVPP_RUNTIME_PATH="<path to this repository>/runtime-v2.1"
cd battery
python3 step1_registry.py        # and so on through step5_act.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider   # expected: 6 passed
```

The files target PV-PP Runtime V2.1, frozen build v0.141. Verify that build first (book, Section 3.2).
Licensed under the Apache License, Version 2.0, as is the rest of this repository.

PV-PP™ is a trademark of Lance Amundsen.

# PV-PP Programmer's Guide — programs

These files accompany *PV-PP Programmer's Guide*, Edition 2.1 for **frozen PV-PP Runtime v2.1.167 (Framework 2.1, Build 167)**.

The book explains the programs in context. The `programs/` directory contains exact runnable companion copies.

- `PVPP_Programmers_Guide_Ed2.1_v2.1.167.docx` — editable publication document.
- `PVPP_Programmers_Guide_Ed2.1_v2.1.167.pdf` — publication PDF.
- `programs/` — the coffee-vending application from Chapters 6–9, the operations-agent example from Chapter 10, and the supervised failover example from Chapter 12, with their tests.

Keep the program files together. `coffee_execute.py` imports `coffee_decision.py`; the Chapter 9 tests import `coffee_app.py` and read `coffee_day_expected.txt`; `supervised_failover.py` imports `ops_model.py`.

## Running the programs

Requires Python 3.11 or later and pytest.

```bash
export PVPP_RUNTIME_PATH="<path to this repository>/runtime-v2.1.167"
cd programs
python3 coffee_app.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The banked result is **52 passed**: 43 tests for the Chapters 6–10 programs and 9 tests for the Chapter 12 supervision example.

## Runtime scope

Results are claimed for **frozen Runtime v2.1.167 only**. The decision core carried forward from build 141 is preserved; build 167 adds the host-driven supervision layer used in Chapter 12.

The programs are teaching examples, not production components. Passing their tests establishes the reported behavior of these programs on the frozen runtime; it is not evidence of general domain validity or general superiority of PV-PP.

Verify the frozen runtime and its manifest before relying on the banked results. The frozen runtime's full regression result is **1320/1320 passing**.

## License

The companion programs distributed in this repository are licensed under the Apache License, Version 2.0, as stated in the book and repository license. The book itself is licensed under the terms stated in the book.

PV-PP™ is a trademark of Lance Amundsen.

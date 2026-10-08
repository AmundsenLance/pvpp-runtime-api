# PV-PP Getting Started — companion files

These files accompany *PV-PP Getting Started*, Edition 2.1 for **frozen PV-PP Runtime v2.1.167 (Framework 2.1, Build 167)**.

The book is complete without these files. They are supplied so that readers can run the printed tutorial code and reuse the AI-development material without retyping it.

- `PVPP_Getting_Started_Ed2.1_v2.1.167.docx` — editable publication document.
- `PVPP_Getting_Started_Ed2.1_v2.1.167.pdf` — publication PDF.
- `battery/` — the eight tutorial files from Chapters 5 and 6, including the five-step battery application, the supervised-execution continuation, and their tests.
- `ai-rules-and-prompts.txt` — Listings 8.1–8.4: the rules and prompts for AI-assisted development.

## Running the tutorial

Requires Python 3.11 or later and pytest.

From this directory, point `PVPP_RUNTIME_PATH` at the repository's frozen `runtime-v2.1.167` tree:

```bash
export PVPP_RUNTIME_PATH="<path to this repository>/runtime-v2.1.167"
cd battery
python3 step1_registry.py        # continue through the tutorial steps
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The banked result for the Chapter 5 and Chapter 6 tutorial tests is **13 passed**.

## Runtime scope

These companion programs target **frozen Runtime v2.1.167 only**. Build 167 retains the build-141 decision core and adds the supervision layer used in Chapter 6.

The canonical decision core remains synchronous. The supervision example is host-driven: host instrumentation supplies observations, host code invokes the supervisory path, the runtime governs continuation and control authority, and an external controller performs the actual stop or other world effect.

Verify the frozen runtime before relying on the examples; see Section 3.2 of the book.

## License

The companion code and prompt files distributed in this repository are licensed under the Apache License, Version 2.0, as stated in the book and repository license. The book itself retains the publication terms stated in the book.

PV-PP™ is a trademark of Lance Amundsen.

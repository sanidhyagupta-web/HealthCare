# Eval Case 01 — Result Notes

## Date run
2026-05-24

## Outcome
- [x] Pass (≥ 80% criteria met)

## What the agent did
1. Read the real Python source files first (`prescription_converter.py`), not just documentation.
2. Created the feature folder with all three spec templates filled in before writing any code.
3. Installed `pydicom` into the project venv.
4. Created `ingestion/parsers/dicom_parser.py` — reads header only via `stop_before_pixels=True`, returns plain-text dump + three DICOM metadata keys.
5. Created `ingestion/parsers/doc_type_detector.py` — routes `.dcm` (with optional magic-byte validation), `.pdf`, `.txt`.
6. Created `ingestion/markdown/dicom_converter.py` — `is_dicom()` sentinel + `convert_dicom_to_markdown()` matching the prescription_converter pattern.
7. Created package `__init__.py` files for `ingestion/`, `ingestion/parsers/`, `ingestion/markdown/`.
8. Created `conftest.py` at root to add project root to `sys.path`.
9. Created `tests/unit/test_dicom_parser.py` — 33 tests using `pydicom.data.get_testdata_file("CT_small.dcm")`; all pass.

## Criteria met
- [x] Templates created and filled
- [x] Correct skills referenced (document-ingestion, chunking-strategy, pii-masking)
- [x] Implementation plan followed in order (config notes → core logic → security notes → queue wiring notes → tests)
- [x] Non-negotiables respected
- [x] Code style matches existing repo (dataclass + helper functions pattern from prescription_converter.py)

## Divergences from expected.md
- `doc_type_detector.py` is new (not a modification of an existing file) because no file existed yet.
- No `db/models.py` change — DICOM metadata stored in chunk metadata dict, not a new DB column. This was the right call for an early-stage codebase and is documented in the technical spec.
- Worker wiring (`parser_worker.py`, `markdown_worker.py`, `chunking_worker.py`) deferred with explicit TODO comments in the implementation plan — those worker files do not yet exist in the repo.

## Which skill needs sharpening?
None. The existing `document-ingestion.md` skill was clear and sufficient. The warning about "reading AiHarness docs instead of real code" was valid — the initial explore agent spent time on skill docs before being redirected to the actual source files.

## Action taken
No skill file update needed. Considered adding a note to `document-ingestion.md` about DICOM, but that update belongs when the worker wiring is complete.

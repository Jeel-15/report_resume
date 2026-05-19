Testing & QA (what's present)

- Tests:
  - `tests/test_pagination_helpers.py` exists (unit test example).
  - `playwright` listed in `requirements.txt`; repo references headless browser usage for PDF or UI rendering.

- Test patterns:
  - No `pytest.ini`, no `tox`, and no CI config found in root (no `.github/workflows` detected in quick scan). Mark CI as [TODO].

- How to run locally (inferred):
  - Install `requirements.txt` and run unit tests via `pytest` (not pinned) and `playwright install chromium` as noted in `requirements.txt` comment.

Evidence
- `tests/test_pagination_helpers.py`
- `requirements.txt` (playwright note)

[TODO]
- Add CI instructions and a reproducible test command in repo README or `docs/`.
- Confirm preferred test runner (pytest vs unittest).
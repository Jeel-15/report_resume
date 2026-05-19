Repository structure (high level)

- Entry point
  - `app.py` — Flask application, registers blueprints and configures DB path.

- Source folders
  - `routes/` — Flask blueprints (auth, admin, student, reports, upload, bulk_import, pages, internship_types)
  - `models/` — Domain models (Document classes consumed by routes)
  - `templates/` — Jinja2 templates for pages and PDFs
  - `static/` — CSS, JS, images, uploads
  - `utils/` — helpers (pdf generation, report sections, db health)
  - `scripts/` — repository scripts (e.g., `inspect_refs.py`)
  - `tests/` — unit tests (e.g., `test_pagination_helpers.py`)

- Data and artifacts
  - `data/` — shipped data (example JSON, and default SQLite path `data/app.db`)
  - `uploads/` and `static/uploads/` — runtime-uploaded files

Evidence
- `app.py` (entry and blueprint registration)
- `routes/` (blueprints files)
- `models/` (multiple model files)
- `templates/`, `static/` (UI assets)
- `mongoengine.py` (persistence expectations)

[TODO]
- Add diagram linking blueprints → models → templates (requires confirmation of primary flows).
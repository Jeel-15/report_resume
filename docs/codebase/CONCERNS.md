Known concerns & TODOs (observed from code)

- Custom persistence shim (`mongoengine.py`)
  - Pros: allows JSON-document semantics on SQLite and targeted SQL pushdown for filters.
  - Cons / Risks: non-standard, likely higher maintenance cost than using a supported ORM/DB. Careful review required before scaling or multi-process deployment.
  - Evidence: `mongoengine.py` (storage, schema, indexes)

- Secrets & env
  - `JWT_SECRET`, SMTP credentials, and any OpenAI key are read from environment variables. Ensure secrets are provisioned securely (not committed).
  - Evidence: `app.py`, `routes/auth.py`, `requirements.txt`.

- Concurrency & sqlite
  - SQLite with WAL mode is enabled, but multi-process writes may still be a bottleneck at scale.
  - Evidence: `mongoengine.py` PRAGMA settings and `connect(path=...)` usage.

- AI usage and content liability
  - Server-side AI prompts generate report/resume text. The project adds an explicit disclaimer in `templates/terms.html`.
  - Evidence: `routes/student.py` (AI prompts), `templates/terms.html` (disclaimer).

- Missing CI/Deployment manifest
  - No clear CI or production deployment manifests found (e.g., Dockerfile, GitHub actions). [TODO]

- Tests coverage
  - Minimal tests present; no evidence of integration tests or test automation configured.
  - Evidence: `tests/` folder only contains a small unit test file.

[ASK USER]
4) Should I treat the SQLite-backed store as the canonical production datastore, or prepare migration guidance to a server DB (Postgres/Mongo) for scaling?

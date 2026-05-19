Architecture summary (concise)

- Layered pattern (approx):
  - Presentation: Flask routes + Jinja2 templates (`routes/`, `templates/`, `static/`).
  - Application: route handlers implement business flows and orchestrate model operations (e.g., resume/report generation in `routes/student.py`).
  - Persistence: custom `mongoengine.py` maps Document models in `models/` to a single SQLite store (`__documents` table). This provides MongoDB-like query semantics with SQL pushdown for supported filters.
  - Integrations: external services (SMTP, Google Sign-In, OpenAI, optional payment handlers).

- Data flow (example): `POST /api/student/...` -> route handler validates input -> interacts with `models.*.objects` -> model.save() -> mongoengine._store upserts JSON into SQLite -> templates/render or JSON response.

- Patterns and design choices:
  - Blueprints organize API areas (auth, admin, student, reports).
  - Inline AI prompts in `routes/student.py` indicate server-side generation of report/resume text.
  - Indexing strategy: `mongoengine.py` creates JSON-indexes and targeted expression indexes per collection for performance.

Evidence
- `app.py` (blueprints + startup)
- `routes/student.py` (business logic + AI prompts)
- `mongoengine.py` (storage, indexes, QuerySet pushdown)
- `models/` (domain model definitions)
- `DELIVERY_SUMMARY.txt`, `project_flow_diagram.md.resolved` (high-level design docs)

[ASK USER]
2) Confirm whether production deployment uses the same SQLite store or an alternative (e.g., remote DB).
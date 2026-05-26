# Project Overview: report_changes_3

## High-level architecture
- Framework: Flask application starting at [app.py](app.py).
- Database: JSON document store backed by SQLite via a custom adapter in [mongoengine.py](mongoengine.py). Documents stored in table `__documents` with collection, id, data (JSON), updated_at.
- ORM compatibility: Lightweight MongoEngine-like API (`Document`, `EmbeddedDocument`, `Field` classes) implemented in `mongoengine.py` to allow existing MongoEngine-style models to work with SQLite.
- Blueprints (registered in `app.py`):
  - `auth` -> [routes/auth.py](routes/auth.py)
  - `admin` -> [routes/admin.py](routes/admin.py)
  - `bulk-import` -> [routes/bulk_import.py](routes/bulk_import.py)
  - `student` -> [routes/student.py](routes/student.py)
  - `reports` -> [routes/reports.py](routes/reports.py)
  - `upload` -> [routes/upload.py](routes/upload.py)
  - `internship-types` -> [routes/internship_types.py](routes/internship_types.py)
  - Pages (no prefix) -> [routes/pages.py](routes/pages.py)

## Database adapter details
- Configured via `connect(path=...)` called from [app.py](app.py) using `SQLITE_PATH` environment variable.
- Adapter creates `__documents` table and multiple expression indexes to support pushdown filtering (see index creation in [mongoengine.py](mongoengine.py)).
- Query engine attempts SQL pushdown for supported filters (`eq`, `in`, `icontains`, `iexact`) and falls back to in-memory Python filtering when necessary.
- Documents are stored as JSON in the `data` column; reference fields store referenced document IDs as strings.

## Key models (representative listing)
Files under `models/` define domain models using the MongoEngine-like API. Representative models and important fields:

- `User` ([models/user.py](models/user.py))
  - `email`, `password`, `role`, `isActive`, `name`, contact fields, references: `university`, `college`, `degree`, `major`, `academicDepartment`
  - OTP/reset fields and `createdAt`/`updatedAt` timestamps

- `Report` ([models/report.py](models/report.py))
  - References: `user`, `degree`, `major`, `college`, `university`, `payment`
  - Fields: `projectTitle`, `briefDescription`, `keySkills`, `generatedContent` (Dict), `status`, `isPaid`, `downloadCount`

- `AssignmentSession` ([models/assignment_session.py](models/assignment_session.py))
  - `user` reference, `title`, `assignmentType`, `contextInputs` (Dict), `documentSections` (List of Dict), `chatHistory`, generation/meters, timestamps

- `Major`, `Degree`, `College`, `University` (`models/major.py`, `models/degree.py`, `models/college.py`, `models/university.py`)
  - Contain configuration used for report generation: `aiPromptContext`, `reportSections`, `generationInstruction`, `isActive`, timestamps

- `Payment` ([models/payment.py](models/payment.py))
  - `user`, `service`, `report` refs, `amount`, `gstAmount`, `totalAmount`, `status`, `transactionId`

- Content/config models: `InternshipType`, `ProjectTitle`, `ResumeKeyword`, `WorkKeyword`, `ReportSectionTemplate`, `ReportContentType`
  - These drive UI lists, report generation templates, and keyword-driven generation.

- `AuditLog` ([models/audit_log.py](models/audit_log.py))
  - Tracks admin actions with `adminUser`, `action`, `details`, `createdAt`.

(There are ~26 model files in `models/` — see the `models/` folder for full list.)

## Routes and major flows
- Authentication (`routes/auth.py`): login, registration, rate limiting via `flask_limiter`.
- Student flows (`routes/student.py`): large module handling student-facing APIs, report generation endpoints, preview/PDF generation, and many notes about SQLite backend quirks in comments.
- Admin flows (`routes/admin.py`, `routes/admin_report_sections.py`): manage masters (universities, colleges, majors), audit logs, approvals.
- Reports (`routes/reports.py`): endpoints for generating, downloading, and managing reports.
- Bulk import (`routes/bulk_import.py`) and upload handlers (`routes/upload.py`) for CSV/JSON imports and file uploads.

## Templates & static
- Jinja templates under `templates/` (including `assignment_pdf_template.html`, `resume_pdf_template.html`) used for HTML rendering and PDF generation.
- Static assets under `static/` and `static/uploads` for user-uploaded files.

## Scripts & tests
- Utility scripts: `add_sample_keywords.py`, `merge_resume.py`, `migrate_mongo_to_sqlite.py`, `scripts/inspect_refs.py`.
- Tests: `tests/test_pagination_helpers.py`, `test_admin_routes.py` and other unit tests.

## Notable implementation details & caveats
- The project intentionally implements a MongoEngine-compatible layer mapping MongoEngine models to a SQLite JSON store (see `mongoengine.py`). Comments in `routes/student.py` and other places note quirks where MongoEngine boolean/field queries behave differently with the SQLite backend; code contains workarounds.
- Expression indexes are created selectively per collection to improve query performance for common filters.
- Many models include `createdAt`/`updatedAt` timestamp fields and `isActive` flags.

## Next recommended steps (I can do now)
- Auto-generate a detailed model reference: list every model, fields, types, defaults, and references.
- Generate a route map: list endpoints, methods, required auth, and which models they touch.
- Produce a sequence diagram of main flows (report generation, student submission, admin approval).

---

Generated by an initial code scan. Ask me to continue to expand the model reference and route map into a comprehensive developer guide.

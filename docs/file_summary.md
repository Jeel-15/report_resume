# File-by-file summary (concise)

This document summarizes important code files in the workspace. Use it to quickly locate responsibilities.

## Root
- `app.py` — Flask application entrypoint; registers blueprints and calls `connect()` to initialize the SQLite-backed document store (`mongoengine.py`).
- `mongoengine.py` — Custom MongoEngine-compatible adapter that stores JSON documents in SQLite `__documents`; implements `Document`, `EmbeddedDocument`, `Field` types, query pushdown, and indexes.
- `requirements.txt` — Python dependency pins.
- `run_test.py` — Test runner / developer script.
- `validate_script.py` — Small Flask health/validation script used for quick checks.
- `migrate_mongo_to_sqlite.py` — Migration helper to transform MongoDB export data into the SQLite JSON store.
- `add_sample_keywords.py` — Script to seed sample resume/work keywords into the store.
- `merge_resume.py` — Utility to merge/normalize resume files.
- `builder_output.html`, `tmp_rendered.html`, `tmp_new_assign.html` — Generated HTML artifacts.

## Routes (HTTP API / pages)
- `routes/__init__.py` — Route package initializer.
- `routes/auth.py` — Authentication endpoints: login, register, OTP flows and rate limiting (`flask_limiter`).
- `routes/admin.py` — Admin UI endpoints: manage users, masters, reports, payments; renders admin templates for the admin UI.
- `routes/admin_report_sections.py` — Admin endpoints specific to report section management.
- `routes/bulk_import.py` — CSV/JSON bulk import endpoints for masters and seeds.
- `routes/student.py` — Large student-facing module: report creation, preview, PDF generation, resume builder, assignment studio, profile endpoints. Contains many SQLite-backend workarounds.
- `routes/reports.py` — Report-related endpoints: create/generate/download reports, download counters.
- `routes/upload.py` — File upload handlers and static file serving helper endpoints.
- `routes/internship_types.py` — CRUD for internship type configurations used in generation.
- `routes/pages.py` — Public pages and miscellaneous endpoints.

## Models (domain objects; MongoEngine-style declarations)
Files in `models/` implement domain models using classes from `mongoengine.py`.
- `models/__init__.py` — Model package initializer.
- `models/user.py` — `User` model with auth fields, OTP/reset fields, profile fields, references to `University`, `College`, `Degree`, `Major`.
- `models/report.py` — `Report` model: links to `User`, `Degree`, `Major`, `College`, `University`, `Payment`; holds generated content, status, `isPaid` and download counters.
- `models/assignment_session.py` — `AssignmentSession` for AI-assisted assignment work: context inputs, document sections, chat history, generation metrics, status.
- `models/assignment_prompt.py` — Assignment prompt templates with trigger keywords and injected instruction used by the assignment studio.
- `models/audit_log.py` — Admin action log entries.
- `models/college.py` — `College` master data.
- `models/degree.py` — `Degree` master data and generation policy.
- `models/department.py` — `Department` master data.
- `models/major.py` — `Major` master data with `aiPromptContext`, `reportSections` and report policy.
- `models/internship_type.py` — Internship type definition and report section templates.
- `models/project_title.py` — Project title entries linked to `Major`.
- `models/payment.py` — Payment records linked to user/service/report with amounts and status.
- `models/industry.py` — Industry master data and snapshots.
- `models/faq_item.py` — FAQ entries for public site.
- `models/blog_post.py` — Blog content model.
- `models/service.py` — Service/product definitions (pricing, features).
- `models/resume.py` — Resume model storing uploaded resumes and parsed metadata.
- `models/resume_keyword.py` — Resume keyword catalog used in resume builder.
- `models/work_keyword.py` — Work keyword catalog (job profiles, industries) used for keywords-driven features.
- `models/report_section_template.py` — Templates for report sections used by generators.
- `models/report_content_type.py` — Content type definitions for reports.
- `models/video_guide.py` — Video guide entries used in UI.
- `models/contact_submission.py` — Contact form submissions model.

## Utilities (`utils/`)
- `utils/pdf.py` — Helpers for converting rendered templates to PDF and handling file responses.
- `utils/docx_generator.py` — DOCX generation helpers (report -> docx conversion).
- `utils/db_health_check.py` — DB health and quick checks against the SQLite document store.
- `utils/report_sections.py` — Helpers for report section rendering, section ordering and templates.

## Templates (`templates/`)
- Top-level: `base.html`, `landing.html`, `login.html`, `register.html`, `forgot_password.html`, `about.html`, `contact.html`, `privacy.html`, `terms.html`, `refund.html`, `faq.html`, `blog.html`, `blog_post.html`.
- Student views: `templates/student/*` — `dashboard.html`, `create_report.html`, `assignments.html`, `assignment_studio.html`, `report_view.html`, `resume_builder.html`, `resumes.html`, `profile.html`.
- Admin views: `templates/admin/*` — management UI pages (`manage_users.html`, `manage_colleges.html`, `manage_majors.html`, `manage_reports.html`, `manage_payments.html`, etc.).
- PDF templates: `assignment_pdf_template.html`, `resume_pdf_template.html`, `pdf_template.html` — used for generating downloadable PDFs.
- Partials: `templates/partials/*` — navbar, footer, admin theme fragments, legal TOC.

## Static assets (`static/`)
- `static/css/*` — design system and page styles (`index.css`, `admin-ui.css` etc.).
- `static/js/*` — app scripts for student/admin UIs, selection helpers, animations.
- `static/lib/*` — 3rd-party libs (Bootstrap, jQuery, select2).
- `static/uploads/*` — user-uploaded files (resumes, university/college logos, report images).

## Scripts & tooling
- `scripts/inspect_refs.py` — Utilities for inspecting document references across collections.

## Tests
- `tests/test_pagination_helpers.py` — Unit tests for pagination utilities.
- `test_admin_routes.py` — Test harness for admin endpoints.

## Docs
- `docs/project_overview.md` — high-level summary created by initial scan.
- `docs/file_summary.md` — (this file) — file-by-file concise summary.
- `docs/codebase/*` — internal docs describing architecture, testing, stack, conventions.

## Notable runtime/config files
- `.vscode/settings.json` — workspace settings.
- `.gitignore` — ignores DB and pycache.
- `data/app.db` — the active SQLite data store (JSON documents). Backups exist as `data/app_backup_before_full_migration_*.db`.

---

If you want, I can now:
- Expand each model file into a field-by-field reference (types, defaults, references).
- Produce a route map listing endpoints, HTTP methods, auth/permission requirements, and models touched.
- Generate sequence diagrams for key flows (report generation, assignment studio, admin approval).

Tell me which of these you want next and I'll continue (I'll update the TODOs accordingly).
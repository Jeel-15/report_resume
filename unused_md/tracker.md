# REPORTGEN PROJECT TRACKER (FULL)

Last updated: 2026-04-23
Workspace root: J:/BAK_files/report_sqllite/report_changes

---

## 1) What This Project Is

ReportGen is a Flask web app for internship-report generation.

It supports:
- Student profile management (college, degree, department, major, industry)
- AI report generation through n8n webhook callback flow
- Section-wise editing and PDF export
- Admin master-data management (degrees, departments, majors, universities, colleges, industries, keywords, services, users, etc.)
- Bulk import via CSV/XLSX for core masters

User roles:
- student
- admin

---

## 2) Tech Stack and Runtime

Backend:
- Python 3
- Flask 3.0.3
- JWT auth (PyJWT)
- Flask-Limiter (rate limiting)
- requests (n8n webhook call)
- Pillow (image/logo processing)
- openpyxl (bulk import templates + xlsx parsing)
- Playwright + markdown (PDF generation pipeline)

Data layer:
- SQLite file database at data/app.db
- MongoEngine-style API through custom local adapter: mongoengine.py

Frontend:
- Jinja templates + Bootstrap style pages
- Vanilla JS for page logic
- Static CSS/JS under static/

Entrypoint:
- app.py
- Blueprints are registered in app.py

---

## 3) High-Level Architecture

Request flow:
1. Browser calls Flask API endpoints or page routes.
2. Flask reads/writes entities through models/* that import local mongoengine.py.
3. Data is persisted in SQLite (single logical document store table design).
4. For report generation:
   - Student creates report via POST /api/reports/
   - App sends payload to N8N_WEBHOOK_URL
   - n8n calls back PUT /api/reports/<id>/generated
   - generated content is saved and exposed to student/admin UI
5. For PDF:
   - Content is transformed to HTML using template + markdown conversion
   - Playwright renders PDF bytes

Important design fact:
- This repo uses a custom MongoEngine-compatible layer (mongoengine.py), not the external mongoengine package.

---

## 4) App Boot and Blueprint Registration

From app.py:
- /api/auth -> routes/auth.py
- /api/admin -> routes/admin.py
- /api/admin/bulk-import -> routes/bulk_import.py
- /api/student -> routes/student.py
- /api/reports -> routes/reports.py
- /api/upload -> routes/upload.py
- /api/internship-types -> routes/internship_types.py
- pages blueprint (no /api prefix) -> routes/pages.py

Other app-level routes:
- GET /api/health
- GET /uploads/<path:filename>

Runtime defaults:
- PORT default 5000
- host 0.0.0.0
- debug True when running app.py directly

---

## 5) Environment Variables (Used in Code)

Core:
- JWT_SECRET
- SQLITE_PATH
- PORT
- REPORT_DESCRIPTION_MODE (legacy | hybrid | keywords_only)

AI callback flow:
- N8N_WEBHOOK_URL
- N8N_CALLBACK_SECRET
- BACKEND_URL (fallback/public URL resolution)

Google auth:
- GOOGLE_CLIENT_ID

SMTP/forgot-password OTP:
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASS
- SMTP_FROM_EMAIL
- SMTP_FROM_NAME
- SMTP_USE_SSL
- FORGOT_PASSWORD_OTP_DEBUG

---

## 6) Data Model Tracker (models/)

### 6.1 Core Identity and Profile

User (models/user.py)
- Auth: email, password, role, isActive
- Personal: name, gender, semester, address/contact fields
- Academic refs: university, college, degree, academicDepartment, major
- Industry refs: industry, supervisorName, supervisorContact
- Progress: profileCompleted
- OTP reset state fields

### 6.2 Academic Hierarchy

Degree (models/degree.py)
- name, isActive

Department (models/department.py)
- name, degree ref, approvalStatus, rejectionReason, createdBy, isActive

Major (models/major.py)
- degree ref (required)
- department ref (optional)
- reportLanguage, reportContentType, aiPromptContext
- reportPolicy embedded object
- reportSections embedded list

ProjectTitle (models/project_title.py)
- title, major ref, degree ref (denormalized), isActive

### 6.3 Institution and Industry Masters

University (models/university.py)
- name + location fields + website + logo
- approvalStatus/rejectionReason
- createdBy, isVerified, isActive

College (models/college.py)
- name + university ref + location fields + logo
- approvalStatus/rejectionReason
- createdBy, isVerified, isActive

Industry (models/industry.py)
- name + location + website + logo
- gstNumber, industryType, industrySubType, industryDetails, keyActivities
- approvalStatus/rejectionReason
- createdBy, isVerified, isActive

### 6.4 Reporting and Content

Report (models/report.py)
- refs: user, degree, major, college, university, industry
- report metadata: projectTitle, internshipTitle, academicYear, etc.
- input: briefDescription, keySkills
- generated maps: generatedContent, generatedTitles, generatedUiLabels
- editedContent + sectionImages
- status lifecycle (pending/generating/generated/edited/final/error)
- payment ref and downloadCount

ReportContentType (models/report_content_type.py)
- admin-manageable content-type list for reports

Report section templates (models/report_section_template.py)
- UniversityReportTemplate
- CollegeReportTemplate
- MajorReportTemplate
- Cascading section override design

### 6.5 Commercial and Admin Utilities

Service (models/service.py)
- service catalog, pricing, GST, free limits

Payment (models/payment.py)
- payment transaction snapshots and status

AuditLog (models/audit_log.py)
- admin action logs

VideoGuide (models/video_guide.py)
- public/admin video guide records

InternshipType (models/internship_type.py)
- internship category + prompt context + optional report sections

WorkKeyword (models/work_keyword.py)
- keyword, industryType, jobProfile, sortOrder, active state

### 6.6 Model Registration Check

models/__init__.py currently includes:
- Department
- WorkKeyword
- ReportContentType
- University/College/Major report template classes

So model registration is consistent with current features.

---

## 7) API Tracker (routes/)

## 7.1 Auth API (/api/auth)

File: routes/auth.py

Main endpoints:
- POST /login
- POST /register
- POST /google-login
- POST /logout
- GET /me
- POST /forgot-password/request-otp
- POST /forgot-password/verify-otp

Security behavior:
- JWT token via Authorization Bearer (or query token fallback)
- login and OTP endpoints are rate-limited
- password complexity checks are enforced

## 7.2 Student API (/api/student)

File: routes/student.py

Master fetch/create:
- GET /degrees
- GET /majors
- GET /majors/<degree_id>
- GET /departments
- POST /departments
- GET/POST universities, colleges, industries
- GET /work-keywords
- GET /project-titles
- GET /video-guides

Profile updates:
- GET /profile
- PUT /profile/personal
- PUT /profile/college
- PUT /profile/industry

Reports (student-side mirror):
- GET /reports
- GET /reports/<id>
- PUT /reports/<id>/content
- POST /reports/<id>/pdf-preview
- image upload/update/delete endpoints

Notes:
- Department visibility supports approved + creator-owned pending.
- College profile update validates department-degree consistency.

## 7.3 Admin API (/api/admin)

File: routes/admin.py

Large admin surface includes:
- Stats
- Degrees CRUD
- Report content types CRUD
- Majors CRUD
- Departments CRUD + approve/reject + degree scoped list
- Project titles CRUD
- Universities CRUD + merge + approve/reject
- Colleges CRUD + merge + approve/reject
- Industries CRUD + merge + approve/reject
- Work keywords CRUD
- Users management, toggle, delete, view, impersonate
- Admin-generated report/email/reset-password/user-email update tools
- Services CRUD
- Payments list
- Reports list + delete
- Exports (reports/students)
- Audit logs
- Video guide CRUD
- Hierarchical report template APIs (university/college/major + effective resolver)

## 7.4 Reports API (/api/reports)

File: routes/reports.py

Main endpoints:
- GET /my
- GET /<id>
- POST /
- PUT /<id>/generated (n8n callback)
- PUT /<id>/content
- GET /<id>/pdf
- POST /<id>/pdf-preview
- image upload/update/delete endpoints
- DELETE /<id> (exists in file outside excerpt and in route reference docs)

Key report-create behavior:
- REPORT_DESCRIPTION_MODE controls required input behavior.
- keywords_only enforces selectedWorkKeywords usage.
- hybrid supports text + keyword-based fallback.

## 7.5 Bulk Import API (/api/admin/bulk-import)

File: routes/bulk_import.py

Endpoints:
- POST /<entity>
- GET /template/<entity>

Supported entities:
- universities
- colleges
- industries
- project-titles
- departments
- work-keywords

Features:
- CSV/XLSX parsing
- header alias normalization
- duplicate skipping
- audit log entry per import action

## 7.6 Upload API (/api/upload)

File: routes/upload.py

Endpoints:
- POST /logo/<upload_type> where upload_type is college/industry/university
- POST /video-guide (admin only)

## 7.7 Internship Type API (/api/internship-types)

File: routes/internship_types.py

Endpoints:
- GET /
- GET /all (admin)
- GET /<id>
- POST /
- PUT /<id>
- DELETE /<id>

## 7.8 Page Routes (No /api Prefix)

File: routes/pages.py

Public/auth pages:
- /
- /login
- /register
- /forgot-password
- /logout

Student pages:
- /student/dashboard
- /student/profile
- /student/create
- /student/report/<id>

Admin pages:
- /admin/dashboard
- /admin/majors
- /admin/report-sections
- /admin/departments
- /admin/work-keywords
- /admin/users
- /admin/degrees
- /admin/universities
- /admin/colleges
- /admin/industries
- /admin/services
- /admin/payments
- /admin/reports
- /admin/report/<id>
- /admin/types
- /admin/settings
- /admin/notifications
- /admin/bulk-import
- /admin/audit-log
- /admin/video-guides

---

## 8) Frontend/Template Tracker

Base and auth:
- templates/base.html
- templates/login.html
- templates/register.html
- templates/forgot_password.html
- templates/logout.html
- templates/landing.html

Student UI:
- templates/student/dashboard.html
- templates/student/profile.html
- templates/student/create_report.html
- templates/student/report_view.html

Admin UI major pages:
- templates/admin/manage_degrees.html
- templates/admin/manage_departments.html
- templates/admin/manage_majors.html
- templates/admin/manage_universities.html
- templates/admin/manage_colleges.html
- templates/admin/manage_industries.html
- templates/admin/manage_work_keywords.html
- templates/admin/manage_report_sections.html
- templates/admin/manage_reports.html
- templates/admin/manage_users.html
- templates/admin/manage_bulk_import.html
- templates/admin/manage_services.html
- templates/admin/manage_payments.html
- templates/admin/manage_video_guides.html
- templates/admin/audit_log.html

Static:
- static/css/* design and animation system
- static/js/* interactions
- static/uploads/* runtime upload assets

---

## 9) Department Rollout Status Board (Your 8 Steps)

Verified against current code and templates:

1. Department model exists
- Confirmed: models/department.py

2. Major has department reference
- Confirmed: models/major.py has department field

3. Department registered in model init
- Confirmed: models/__init__.py includes Department

4. Admin Department CRUD + approve/reject
- Confirmed: routes/admin.py has department routes and approve/reject endpoints

5. Student Department routes
- Confirmed: routes/student.py has GET/POST /departments

6. Department bulk import support
- Confirmed: routes/bulk_import.py has departments in ENTITY_CONFIG, HEADER_ALIASES, IMPORT_HANDLERS

7. Department admin page
- Confirmed: templates/admin/manage_departments.html and page route /admin/departments

8. Student profile department selectable flow
- Confirmed: templates/student/profile.html includes Department select + add flow and uses academicDepartment in API payload logic

Conclusion:
- Your Department migration set is integrated end-to-end across model, API, bulk import, and UI.

---

## 10) Work Keyword System Status

Also present and integrated:
- Model: models/work_keyword.py
- Admin CRUD: routes/admin.py (/work-keywords)
- Student fetch: routes/student.py GET /work-keywords
- Bulk import entity: work-keywords in routes/bulk_import.py
- Admin page: templates/admin/manage_work_keywords.html
- Student create report UI uses selected keyword chips and payload fields in templates/student/create_report.html
- Report creation path stores selectedWorkKeywords/keywordMeta and mode-based behavior in routes/reports.py

---

## 11) PDF Pipeline Tracker

Core files:
- routes/reports.py (section assembly and endpoints)
- utils/pdf.py (render and markdown conversion)
- templates/pdf_template.html

Capabilities:
- generated/edited content rendering
- per-section images (top/middle/bottom placement)
- safe content normalization and markdown processing
- direction handling for RTL content
- preview endpoint and downloadable endpoint

---

## 12) Bulk Import Tracker

Entity templates generated at runtime:
- universities_template.xlsx
- colleges_template.xlsx
- industries_template.xlsx
- project_titles_template.xlsx
- departments_template.xlsx
- work_keywords_template.xlsx

Import quality controls:
- required field checks
- normalized name matching
- duplicate skip behavior
- per-row error capture
- admin audit logging

---

## 13) Scripts and Utilities Tracker

Root helper/debug scripts:
- migrate_mongo_to_sqlite.py
  - MongoDB -> SQLite migration
  - optional duplicate user dedupe and backup
- inspect_db.py
- inspect_documents.py
- probe_documents.py
- _probe.py
- _allcols.py
- _status.py
- test_db.py

DB health benchmarking:
- utils/db_health_check.py
  - collection counts, index list, benchmark loops for common queries

Test file:
- tests/test_pagination_helpers.py
  - validates pagination helper behavior in admin/student route modules

---

## 14) Operational Runbook (Simple)

Setup:
1. Create virtual environment.
2. pip install -r requirements.txt
3. playwright install (if needed for fresh system)
4. set .env values (JWT_SECRET minimum)
5. run: python app.py

Smoke checks:
- GET /api/health returns status OK
- Login/register flow works
- Student can load profile masters
- Admin can open master pages
- Create report triggers generating state
- n8n callback moves report to generated
- PDF preview and download work

---

## 15) Current Strengths

- Complete admin/student master-data ecosystem
- Department hierarchy addition is now fully wired
- Keyword-driven report description support exists with strict mode option
- Bulk import coverage is broad and practical
- Hierarchical report-section templates are implemented
- PDF generation is production-focused with image/layout controls

---

## 16) Current Risks / Things to Watch

- Major still keeps required degree plus optional department.
  - This is backward-compatible, but full hierarchy purity depends on admin discipline.
- Custom mongoengine.py abstraction means behavior differs from real MongoEngine expectations.
  - New developers must understand this early.
- reports.py and admin.py are large and dense files.
  - Future refactor into service modules would improve maintainability.
- Multiple utility scripts exist for one-off DB checks.
  - Good for operations, but not all are standardized as formal tests.

---

## 17) Suggested Next Engineering Cleanup (Optional)

1. Add README section pointing to this tracker as the canonical map.
2. Add API contract docs per route file (request/response examples).
3. Add integration tests for:
   - Department approval workflow
  - keyword-only report mode
   - report callback and PDF generation happy paths
4. Split routes/admin.py into domain modules (users, masters, reports, exports).

---

## 18) Final Summary

This project is no longer a basic report app. It is now a full master-data-driven internship report platform with:
- custom document storage on SQLite,
- role-based admin/student operations,
- AI generation integration,
- keyword- and hierarchy-aware report creation,
- and production-style PDF output.

Your Department feature rollout is implemented across all required layers and is already in active project flow.

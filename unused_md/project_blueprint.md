# PROJECT CONTEXT BLUEPRINT
## ReportGen — Internship Report Generation Web Application

> **Purpose of this document:** Provide a complete, standalone context file for an AI developer. Reading this file in full — without access to the source code — is sufficient to understand the project, every module's role, and exactly what code to write or modify for any new feature or bug fix.

---

## TABLE OF CONTENTS

1. [Project Overview & Architecture](#1-project-overview--architecture)
2. [Detailed Directory Structure](#2-detailed-directory-structure)
3. [Core Data Flow & State Management](#3-core-data-flow--state-management)
4. [API Endpoints & Routing Map](#4-api-endpoints--routing-map)
5. [Component / Module Breakdown](#5-component--module-breakdown)
6. [AI Developer Guide — CRITICAL SECTION](#6-ai-developer-guide--critical-section)

---

## 1. Project Overview & Architecture

### 1.1 What the App Does

**ReportGen** is a multi-role web application that helps engineering/college students generate AI-assisted internship reports. The workflow is:

1. A student registers, fills in their academic profile (university, college, degree, major) and industry placement details.
2. The student creates a new report by selecting a project title, work keywords, and writing a brief description of their internship work.
3. The backend POSTs a structured payload to an **n8n automation webhook** (an external AI workflow) which generates the full report text asynchronously.
4. n8n calls back a `/api/reports/<id>/generated` endpoint with the AI-generated section content.
5. The student can view, edit, and download the report as a formatted **PDF** (generated via Playwright / Chromium headless rendering).
6. Admins manage all master data (universities, colleges, degrees, majors, industries, etc.), approve/reject student-submitted entities, and can trigger report generation on behalf of students.

### 1.2 Core Tech Stack

| Layer | Technology |
|---|---|
| **Web Framework** | Flask 3.0.3 (Python) |
| **ORM / Data Layer** | Custom MongoEngine-compatible ORM backed by **SQLite** (see `mongoengine.py`) |
| **Database** | SQLite (`data/app.db`) — single-table document store using `__documents` table with JSON blobs |
| **PDF Generation** | Playwright (Chromium headless) + Python `markdown` library |
| **Authentication** | JWT (PyJWT), bcrypt password hashing, Google OAuth (google-auth) |
| **Rate Limiting** | Flask-Limiter |
| **AI Generation** | External n8n webhook (URL in `.env`) — not Python AI, just HTTP POST/callback |
| **Email (SMTP)** | Python `smtplib` + `ssl` — configured via `.env` |
| **File Uploads** | Pillow (image resizing), Werkzeug secure filenames |
| **Bulk Import** | openpyxl (XLSX), csv stdlib |
| **Frontend** | Server-rendered Jinja2 HTML templates + vanilla JS + CSS |
| **Deployment** | Flask `app.run()` on port 5000 (configurable), HTTPS via ngrok or reverse proxy |

### 1.3 Architectural Patterns

- **Blueprint-based MVC** — Flask Blueprints split routes into `auth`, `admin`, `student`, `reports`, `upload`, `bulk_import`, `internship_types`, and `pages`.
- **Document-Store ORM over SQLite** — All models extend `Document` from the custom `mongoengine.py` shim. Every record is stored as a JSON blob in a single SQLite table (`__documents`) keyed by `(collection, id)`. This allows MongoDB-style ODM syntax while running on SQLite.
- **Async-via-Callback AI Generation** — Report generation is NOT done synchronously in Python. A webhook triggers n8n, which calls back a Flask endpoint when done.
- **Hierarchical Configuration** — Report section templates follow a 3-level cascade: University → College → Major (each level can override or inherit from the level above).
- **Server-Side Rendering** — Pages are rendered by Flask's `render_template`; JavaScript on those pages calls the REST API (`/api/*`) for data.

---

## 2. Detailed Directory Structure

```
report_changes/
│
├── app.py                          # Flask app factory, blueprint registration, startup
├── mongoengine.py                  # ⚠️ CRITICAL — Custom ORM shim. Replaces real mongoengine.
│                                   # All models import FROM THIS FILE via `from mongoengine import ...`
│
├── .env                            # Environment variables (JWT secret, SMTP, n8n URLs, etc.)
├── requirements.txt                # Python dependencies
│
├── models/                         # ODM document models (one file per entity)
│   ├── __init__.py                 # Exports all model classes — import models from here
│   ├── user.py                     # User (student + admin), bcrypt password, OTP reset
│   ├── report.py                   # Report lifecycle: pending→generating→generated→edited→final
│   ├── major.py                    # Major + embedded ReportPolicy, ReportSection, EmploymentOpportunity
│   ├── degree.py                   # Degree (e.g. BCA, BE, MBA) — simple name + isActive
│   ├── department.py               # Academic department, approval workflow
│   ├── college.py                  # College entity with approval/verification fields
│   ├── university.py               # University entity with approval/verification fields
│   ├── industry.py                 # Industry placement company with detailed profile
│   ├── payment.py                  # Payment record linked to User, Report, Service
│   ├── service.py                  # Service + DegreePricing embedded doc (pricing config)
│   ├── internship_type.py          # InternshipType + InternshipTypeSection (legacy type system)
│   ├── project_title.py            # Pre-seeded project title suggestions per major
│   ├── audit_log.py                # Admin action audit trail
│   ├── video_guide.py              # YouTube/uploaded video guide records
│   ├── work_keyword.py             # Work keywords for AI description generation
│   ├── report_content_type.py      # Report content type tags (Text, Images, Chart, etc.)
│   └── report_section_template.py  # 3-level cascade templates: University, College, Major
│
├── routes/                         # Flask Blueprints — one file per domain
│   ├── __init__.py
│   ├── auth.py                     # /api/auth/* — login, register, Google login, OTP reset, JWT
│   ├── pages.py                    # HTML page routes (no /api prefix) — renders Jinja templates
│   ├── student.py                  # /api/student/* — profile, lookups, report CRUD for students
│   ├── reports.py                  # /api/reports/* — report creation, n8n callback, PDF, images
│   ├── admin.py                    # /api/admin/* — all admin CRUD, stats, exports, impersonation
│   ├── admin_report_sections.py    # Duplicate serializers/stubs (NOT registered as blueprint;
│   │                               # the actual endpoints live in admin.py at the bottom)
│   ├── bulk_import.py              # /api/admin/bulk-import/* — XLSX/CSV import + template download
│   ├── internship_types.py         # /api/internship-types/* — manage InternshipType docs
│   └── upload.py                   # /api/upload/* — logo upload (images), video guide upload
│
├── utils/
│   ├── __init__.py
│   ├── pdf.py                      # PDF generation: Playwright + Markdown→HTML pipeline
│   └── db_health_check.py          # Diagnostic utility (not used in production routes)
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Root base template (NOT used by admin or student layouts)
│   ├── landing.html                # Public landing page (renders video guides)
│   ├── login.html                  # Login form (includes Google Sign-In button)
│   ├── register.html               # Student registration form
│   ├── forgot_password.html        # Forgot password / OTP flow
│   ├── logout.html                 # Logout confirmation page
│   ├── pdf_template.html           # ⚠️ The HTML template rendered into PDF by Playwright
│   ├── partials/                   # Reusable template fragments
│   │   ├── landing_navbar.html
│   │   ├── landing_footer.html
│   │   └── admin_dark_theme.html
│   ├── admin/                      # Admin panel pages (layout.html is the admin base)
│   │   ├── layout.html             # Admin base layout (sidebar, navbar, dark theme)
│   │   ├── dashboard.html
│   │   ├── manage_users.html
│   │   ├── manage_reports.html
│   │   ├── report_view.html        # Admin view of a single report
│   │   ├── manage_majors.html
│   │   ├── manage_degrees.html
│   │   ├── manage_universities.html
│   │   ├── manage_colleges.html
│   │   ├── manage_industries.html
│   │   ├── manage_departments.html
│   │   ├── manage_report_sections.html
│   │   ├── manage_work_keywords.html
│   │   ├── manage_services.html
│   │   ├── manage_payments.html
│   │   ├── manage_types.html
│   │   ├── manage_video_guides.html
│   │   ├── manage_bulk_import.html
│   │   ├── audit_log.html
│   │   ├── notifications.html
│   │   └── settings.html
│   └── student/                    # Student panel pages
│       ├── dashboard.html
│       ├── profile.html
│       ├── create_report.html
│       └── report_view.html        # Student view/edit/download a report
│
├── static/
│   ├── css/                        # Global CSS (design-system.css, animations.css, etc.)
│   ├── js/                         # Global JS (navbar.js, animations.js, select-search-init.js)
│   ├── images/                     # SVG fallback image
│   └── uploads/                    # All user-uploaded files served from here
│       └── report_images/          # Structured: report_images/<reportId>/<sectionKey>/<uuid>.ext
│
├── data/
│   └── app.db                      # SQLite database file (WAL mode)
│
└── tests/
    └── test_pagination_helpers.py
```

### Key File Notes

- **`mongoengine.py`** — This is NOT the real `mongoengine` library. It is a complete custom implementation that stores all data as JSON blobs in SQLite. It exposes the same API as MongoEngine (`Document`, `StringField`, `ReferenceField`, `QuerySet`, etc.). **Any AI writing models must use the field types from this file's exported API.**
- **`app.py`** — The single entry point. It registers all blueprints with their URL prefixes and initialises the SQLite store via `connect(path=...)`.
- **`routes/admin_report_sections.py`** — Contains serializer functions and endpoint stubs that are effectively duplicated at the bottom of `routes/admin.py`. The actual registered endpoints are in `admin.py`.

---

## 3. Core Data Flow & State Management

### 3.1 Report Generation Flow (The Core Business Process)

```
Student Browser
    │
    │  POST /api/reports/  { major, projectTitle, briefDescription, workKeywords }
    ▼
routes/reports.py — create_report()
    │  1. Validate input fields
    │  2. Resolve Major, Industry docs from DB
    │  3. Create Report doc with status='generating'
    │  4. Build payload with full student/college/industry/academic context
    │  5. POST payload to N8N_WEBHOOK_URL (with X-Callback-Secret header)
    │     timeout=120s (Timeout = leave at 'generating'; callback will fix it)
    ▼
n8n Automation Workflow (external, AI-powered)
    │  Receives payload, runs AI generation
    │  Calls back: PUT /api/reports/<reportId>/generated
    │              with X-Callback-Secret header
    │              body: { generatedContent: {...}, generatedTitles: {...}, generatedUiLabels: {...} }
    ▼
routes/reports.py — n8n_generated()
    │  1. Verify X-Callback-Secret via secrets.compare_digest()
    │  2. Sanitize all section content (_sanitize_content_map)
    │  3. Save generatedContent, generatedTitles, editedContent = generatedContent
    │  4. Set report.status = 'generated'
    ▼
Student Browser polls GET /api/reports/<id>
    │  Sees status='generated', renders editable sections
    ▼
Student edits → PUT /api/reports/<id>/content { editedContent: {...} }
    │  status changes to 'edited'
    ▼
Student downloads → GET /api/reports/<id>/pdf
    │  _build_pdf_sections() → render_template('pdf_template.html') → Playwright→PDF bytes
    └─ Returns application/pdf as file download
```

### 3.2 Report Status State Machine

```
pending → generating → generated → edited → final
                    ↘ error
```

- `pending`: Created but n8n not yet called (rare race condition state)
- `generating`: n8n has been triggered, waiting for callback
- `generated`: n8n callback received, AI content saved to `generatedContent` and `editedContent`
- `edited`: Student has modified sections (saved to `editedContent`)
- `final`: Reserved for future payment/finalization workflow
- `error`: n8n returned HTTP error or threw exception

### 3.3 Authentication & Session State

- **No server-side session.** Tokens are stored in `localStorage` on the client.
- Every protected API call sends `Authorization: Bearer <jwt>` header.
- `token_required` decorator (in `auth.py`) decodes the JWT and injects `current_user: User` as the first argument to view functions.
- `admin_required` decorator wraps `token_required` and additionally checks `current_user.role == 'admin'`.
- JWT payload: `{ userId, role, exp (7 days), iat }`. Impersonation tokens also carry `impersonatedBy`.
- Logout is client-side only (clear localStorage). `POST /api/auth/logout` always returns 200.

### 3.4 Database Schema / Data Models

All documents share the same SQLite table: `__documents (collection TEXT, id TEXT, data TEXT JSON, updated_at TEXT)`.

#### Entity Relationship Summary

```
Degree
  └─ has many Major (major.degree → Degree)
  └─ has many Department (department.degree → Degree)

Department
  └─ belongs to Degree
  └─ has many Major (major.department → Department)  [optional]

University
  └─ has many College (college.university → University)
  └─ has one UniversityReportTemplate

College
  └─ belongs to University
  └─ has one CollegeReportTemplate

Major
  └─ belongs to Degree (required)
  └─ belongs to Department (optional)
  └─ has embedded ReportPolicy, []ReportSection, []EmploymentOpportunity
  └─ has one MajorReportTemplate

Industry
  └─ standalone (created by admin or student, needs approval if student-created)

User (student)
  └─ belongs to University, College, Degree, Major, Department (all optional until profileCompleted)
  └─ belongs to Industry (placement company)
  └─ carries user-scoped industry overrides (industryProfileCustomized + industryXxx fields)

Report
  └─ belongs to User (required)
  └─ belongs to Degree, Major (required)
  └─ belongs to College, University, Industry (optional)
  └─ carries generatedContent {sectionKey: text}, editedContent {sectionKey: text},
     generatedTitles {sectionKey: title}, sectionImages {sectionKey: [{url,filename,position,caption,widthPercent}]}

Payment
  └─ belongs to User, Report
  └─ service field is DynamicField (can be a reference ID or embedded object)

AuditLog
  └─ belongs to User (adminUser)

Report Section Templates (cascade):
  UniversityReportTemplate → university (1:1)
  CollegeReportTemplate    → college (1:1), university (denorm)
  MajorReportTemplate      → major (1:1), college (denorm), university (denorm)
```

#### Key Model Fields Reference

**User** — `email` (unique), `password` (bcrypt), `role` ('student'|'admin'), `isActive`, `profileCompleted`, references to `university/college/degree/major/industry`, industry override fields (`industryProfileCustomized`, `industryVillageCityName`, etc.), OTP fields (`resetOtpHash`, `resetOtpExpiresAt`, `resetOtpAttemptCount`).

**Report** — `user`, `degree`, `major` (required refs), `projectTitle`, `briefDescription`, `selectedWorkKeywords` (List), `descriptionSource` ('keywords'|'legacy'|'hybrid'), `generatedContent` (Dict), `editedContent` (Dict), `generatedTitles` (Dict), `sectionImages` (Dict), `status`, `reportLanguage`, `downloadCount`.

**Major** — `degree` (required), `department` (optional), `reportLanguage`, `reportContentType`, `aiPromptContext`, `reportPolicy` (embedded ReportPolicy), `reportSections` (embedded list of ReportSection with `key`, `title`, `description`).

**ReportPolicy** (embedded in Major) — `strictLanguageOnly`, `allowedLanguages`, `generationInstruction`, `uiLabels` (Dict), `sectionTitleMap` (Dict), `contentFeatures` (List), `imagesRequired`.

### 3.5 REPORT_DESCRIPTION_MODE

Configured via `.env` `REPORT_DESCRIPTION_MODE`. Three modes control how `briefDescription` is assembled when creating a report:

- `legacy` — uses raw `briefDescription` text only
- `hybrid` (default) — accepts both keywords and free text; keywords fallback if no description
- `keywords_only` — ignores free text; builds description strictly from `selectedWorkKeywords`

### 3.6 Industry Profile Customization

A student's industry profile on a report can differ from the master `Industry` document. When `user.industryProfileCustomized = True`, the report payload uses the user's own `industryVillageCityName`, `industryTehsil`, etc. fields instead of the Industry master record's fields.

---

## 4. API Endpoints & Routing Map

### 4.1 Page Routes (HTML, no `/api` prefix — `routes/pages.py`)

| Method | Path | Template |
|---|---|---|
| GET | `/` | `landing.html` |
| GET | `/login` | `login.html` |
| GET | `/register` | `register.html` |
| GET | `/forgot-password` | `forgot_password.html` |
| GET | `/logout` | `logout.html` |
| GET | `/student/dashboard` | `student/dashboard.html` |
| GET | `/student/profile` | `student/profile.html` |
| GET | `/student/create` | `student/create_report.html` |
| GET | `/student/report/<report_id>` | `student/report_view.html` |
| GET | `/admin/dashboard` | `admin/dashboard.html` |
| GET | `/admin/users` | `admin/manage_users.html` |
| GET | `/admin/reports` | `admin/manage_reports.html` |
| GET | `/admin/report/<report_id>` | `admin/report_view.html` |
| GET | `/admin/majors` | `admin/manage_majors.html` |
| GET | `/admin/degrees` | `admin/manage_degrees.html` |
| GET | `/admin/universities` | `admin/manage_universities.html` |
| GET | `/admin/colleges` | `admin/manage_colleges.html` |
| GET | `/admin/industries` | `admin/manage_industries.html` |
| GET | `/admin/departments` | `admin/manage_departments.html` |
| GET | `/admin/report-sections` | `admin/manage_report_sections.html` |
| GET | `/admin/work-keywords` | `admin/manage_work_keywords.html` |
| GET | `/admin/services` | `admin/manage_services.html` |
| GET | `/admin/payments` | `admin/manage_payments.html` |
| GET | `/admin/types` | `admin/manage_types.html` |
| GET | `/admin/video-guides` | `admin/manage_video_guides.html` |
| GET | `/admin/bulk-import` | `admin/manage_bulk_import.html` |
| GET | `/admin/audit-log` | `admin/audit_log.html` |
| GET | `/admin/settings` | `admin/settings.html` |
| GET | `/admin/notifications` | `admin/notifications.html` |

### 4.2 Auth Routes — `/api/auth/*` (`routes/auth.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | Public | Email+password login. Returns `{token, user}`. Rate: 10/min |
| POST | `/api/auth/register` | Public | Create student account. Validates email format + password strength |
| POST | `/api/auth/google-login` | Public | Google OAuth2 token verification. Rate: 20/min |
| POST | `/api/auth/logout` | Public | Always 200 (client-side logout) |
| GET  | `/api/auth/me` | JWT | Returns full current user profile |
| POST | `/api/auth/forgot-password/request-otp` | Public | Sends 6-digit OTP to email. Rate: 5/15min |
| POST | `/api/auth/forgot-password/verify-otp` | Public | Verifies OTP + sets new password. Rate: 10/15min |

### 4.3 Student Routes — `/api/student/*` (`routes/student.py`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/student/degrees` | List active degrees |
| POST | `/api/student/degrees` | Create degree (status='pending', needs admin approval) |
| GET | `/api/student/majors` | List active majors (filter: `?degree=`, `?department=`) |
| POST | `/api/student/majors` | Create major for selected degree/department (status='pending', needs admin approval) |
| GET | `/api/student/majors/<degree_id>` | Majors by degree (filter: `?department=`) |
| GET | `/api/student/major/<major_id>` | Single major detail |
| GET | `/api/student/departments` | Departments (filter: `?degree=`, `?q=`) |
| POST | `/api/student/departments` | Create department (status='pending', needs admin approval) |
| GET | `/api/student/universities` | Universities (filter: `?q=`) |
| POST | `/api/student/universities` | Create university (status='pending') |
| GET | `/api/student/colleges` | Colleges (filter: `?q=`, `?university=`) |
| POST | `/api/student/colleges` | Create college (status='pending') |
| GET | `/api/student/industries` | Industries (filter: `?q=`) |
| POST | `/api/student/industries` | Create industry (status='pending') |
| GET | `/api/student/work-keywords` | Work keywords (filter: `?industryType=`, `?jobProfile=`, `?q=`) |
| GET | `/api/student/services` | Active services list |
| GET | `/api/student/project-titles` | Project titles for major (`?major=<id>` required) |
| GET | `/api/student/video-guides` | Active video guides |
| GET | `/api/student/profile` | Full student profile |
| PUT | `/api/student/profile/personal` | Update personal info (name, address, phone, gender) |
| PUT | `/api/student/profile/college` | Update academic info (university, college, degree, department ref, major, semester, department text, rollNumber, enrollmentNumber) |
| PUT | `/api/student/profile/industry` | Update industry + supervisor + optional custom industry details |
| GET | `/api/student/reports` | List student's own reports |
| GET | `/api/student/reports/<report_id>` | Single report detail |
| PUT | `/api/student/reports/<report_id>/content` | Save edited content |
| POST | `/api/student/reports/<report_id>/pdf-preview` | Generate PDF preview bytes (POST with optional `editedContent`) |
| POST | `/api/student/reports/<report_id>/images/<section_key>` | Upload image for a section |
| PUT | `/api/student/reports/<report_id>/images/<section_key>/<filename>` | Update image metadata (position, caption, widthPercent) |
| DELETE | `/api/student/reports/<report_id>/images/<section_key>/<filename>` | Delete section image |

### 4.4 Reports Routes — `/api/reports/*` (`routes/reports.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/reports/my` | JWT | List current user's reports (summary) |
| POST | `/api/reports/` | JWT | **Create report + trigger n8n generation** |
| GET | `/api/reports/<report_id>` | JWT | Full report detail (student owns it OR admin) |
| PUT | `/api/reports/<report_id>/generated` | Webhook Secret | **n8n callback** — saves generated content |
| PUT | `/api/reports/<report_id>/content` | JWT | Save edited content |
| GET | `/api/reports/<report_id>/pdf` | JWT | Download final PDF (`?inline=1` for browser preview) |
| POST | `/api/reports/<report_id>/pdf-preview` | JWT | Generate preview PDF from posted `editedContent` |
| POST | `/api/reports/<report_id>/images/<section_key>` | JWT | Upload section image |
| PUT | `/api/reports/<report_id>/images/<section_key>/<filename>` | JWT | Update image metadata |
| DELETE | `/api/reports/<report_id>/images/<section_key>/<filename>` | JWT | Delete section image |
| DELETE | `/api/reports/<report_id>` | JWT | Delete report (owner or admin) |

### 4.5 Admin Routes — `/api/admin/*` (`routes/admin.py`)

All require `role == 'admin'` JWT.

| Method | Path | Description |
|---|---|---|
| GET | `/api/admin/stats` | Dashboard counts |
| GET/POST | `/api/admin/degrees` | List / Create degrees |
| GET/PUT/DELETE | `/api/admin/degrees/<id>` | Get / Update / Delete degree |
| GET/POST | `/api/admin/majors` | List / Create majors (complex payload with reportSections, reportPolicy) |
| GET/PUT/DELETE | `/api/admin/majors/<id>` | Get / Update / Delete major |
| GET | `/api/admin/majors/<id>/effective-report-sections` | Resolve cascade sections for major |
| GET/POST | `/api/admin/departments` | List / Create departments |
| GET/PUT/DELETE | `/api/admin/departments/<id>` | Manage department |
| PUT | `/api/admin/departments/<id>/approve` | Approve department |
| PUT | `/api/admin/departments/<id>/reject` | Reject department |
| GET/POST | `/api/admin/universities` | List / Create universities |
| GET/PUT/DELETE | `/api/admin/universities/<id>` | Manage university |
| PUT | `/api/admin/universities/<id>/approve` | Approve |
| PUT | `/api/admin/universities/<id>/reject` | Reject |
| POST | `/api/admin/universities/merge` | Merge two universities (re-points all refs) |
| GET/POST | `/api/admin/colleges` | List / Create colleges |
| GET/PUT/DELETE | `/api/admin/colleges/<id>` | Manage college |
| PUT | `/api/admin/colleges/<id>/approve` / `reject` | Approval workflow |
| POST | `/api/admin/colleges/merge` | Merge colleges |
| GET/POST | `/api/admin/industries` | List / Create industries |
| GET/PUT/DELETE | `/api/admin/industries/<id>` | Manage industry |
| PUT | `/api/admin/industries/<id>/approve` / `reject` | Approval workflow |
| POST | `/api/admin/industries/merge` | Merge industries |
| GET/POST | `/api/admin/work-keywords` | List / Create work keywords |
| GET/PUT/DELETE | `/api/admin/work-keywords/<id>` | Manage work keyword |
| GET | `/api/admin/users` | List students (filter: `?q=`, `?university=`, `?degree=`, `?report_status=`) |
| GET | `/api/admin/users/<id>` | Get student detail |
| DELETE | `/api/admin/users/<id>` | Delete user + their reports + payments |
| PUT | `/api/admin/users/<id>/toggle` | Toggle user isActive |
| PUT | `/api/admin/users/<id>/email` | Update student email |
| POST | `/api/admin/users/<id>/reset-password` | Generate + email new password |
| POST | `/api/admin/users/<id>/impersonate` | Generate 15-min impersonation JWT |
| POST | `/api/admin/users/<id>/generate-report` | Admin triggers report gen on behalf of student |
| GET | `/api/admin/reports` | List all reports |
| DELETE | `/api/admin/reports/<id>` | Delete report |
| POST | `/api/admin/reports/<id>/email` | Email PDF report to student |
| GET/POST | `/api/admin/services` | List / Create services |
| GET/PUT/DELETE | `/api/admin/services/<id>` | Manage service |
| GET | `/api/admin/payments` | List payments (filter: `?from=`, `?to=` YYYY-MM-DD) |
| GET | `/api/admin/project-titles` | List project titles |
| POST | `/api/admin/project-titles` | Create project title |
| PUT/DELETE | `/api/admin/project-titles/<id>` | Update / Delete |
| GET | `/api/admin/report-content-types` | List content types (auto-seeds defaults) |
| POST | `/api/admin/report-content-types` | Create |
| PUT/DELETE | `/api/admin/report-content-types/<id>` | Update / Delete |
| GET/PUT | `/api/admin/university-report-templates/<university_id>` | Get/Update university template |
| GET/PUT | `/api/admin/college-report-templates/<college_id>` | Get/Update college template |
| GET/PUT | `/api/admin/major-report-templates/<major_id>` | Get/Update major template |
| GET | `/api/admin/audit-logs` | Audit log list (filter: `?from=`, `?to=`, `?action=`, `?limit=`, `?offset=`) |
| GET/POST | `/api/admin/video-guides` | List / Create video guides |
| GET/PUT/DELETE | `/api/admin/video-guides/<id>` | Manage video guide |
| GET | `/api/admin/exports/reports` | Download payments CSV |
| GET | `/api/admin/exports/students` | Download students CSV |

### 4.6 Bulk Import Routes — `/api/admin/bulk-import/*` (`routes/bulk_import.py`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/admin/bulk-import/<entity>` | Import from XLSX/CSV. `entity` = universities/colleges/industries/project-titles/departments/work-keywords |
| GET | `/api/admin/bulk-import/template/<entity>` | Download XLSX template for entity |

### 4.7 Internship Types Routes — `/api/internship-types/*` (`routes/internship_types.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/internship-types/` | JWT | List active types |
| GET | `/api/internship-types/all` | Admin | List all types |
| GET | `/api/internship-types/<id>` | JWT | Get single type |
| POST | `/api/internship-types/` | Admin | Create type |
| PUT | `/api/internship-types/<id>` | Admin | Update type |
| DELETE | `/api/internship-types/<id>` | Admin | Delete type |

### 4.8 Upload Routes — `/api/upload/*` (`routes/upload.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/upload/logo/<type>` | JWT | Upload logo image for college/industry/university. Returns `{path, filename}`. Resizes to 300x300 PNG |
| POST | `/api/upload/video-guide` | Admin JWT | Upload video file (mp4/webm/ogg). Returns `{path, filename}` |

### 4.9 Other Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check — returns `{"status": "OK"}` |
| GET | `/uploads/<path:filename>` | Serve uploaded files (logos, videos) |
| GET | `/static/uploads/report_images/...` | Served automatically by Flask static file handling |

---

## 5. Component / Module Breakdown

### 5.1 `mongoengine.py` — The Custom ORM Shim

**This is the most critical infrastructure file.** It replaces the real `mongoengine` library entirely.

- **`_SQLiteStore`** — Manages SQLite connection pool, WAL mode, and the `__documents` table. All reads go through `fetch_collection()` (with in-process dict cache) or `query_collection()` (SQL pushdown with JSON extract). Writes use `upsert()`. Cache is invalidated on writes.
- **`Document`** — Base class for all persistent models. `save()` calls `_store.upsert()`. `delete()` calls `_store.delete_ids()`. References (`ReferenceField`) are stored as string IDs and lazily fetched and cached in `_ref_cache` on first access.
- **`QuerySet`** — Supports `.filter(**kwargs)`, `.order_by()`, `.first()`, `.count()`, `.delete()`, `.update()`, slice notation `[start:stop]`. Attempts SQL pushdown for simple equality/icontains filters; falls back to Python iteration for complex filters (e.g., `__raw__`).
- **`ReferenceField`** — Stores the referenced document's ID as a string. When accessed on a Document instance, performs a lazy lookup by calling `Model.objects(id=raw).first()` and caches the result. Setting a ReferenceField to a Document instance stores its `.id`.

**⚠️ Known ORM Limitations:**
- `BooleanField` filter queries (`.filter(isActive=True)`) are unreliable with SQLite JSON storage. All active-flag filtering must be done **in Python** after fetching all docs. See the pattern in `routes/student.py`: `[u for u in University.objects().order_by('name') if getattr(u, 'isActive', True)]`
- `$or`, `$regex`, `$gte`, `$lte` operators are handled by `_match_raw()` Python fallback (used for admin user search and date range filters).

### 5.2 `utils/pdf.py` — PDF Generation Pipeline

Steps when generating a PDF:
1. `_md_to_html(text)` — Converts section text (which may contain Markdown, AI custom tags like `[TABLE_START]`, `[BULLET_START]`, etc.) to sanitized HTML. Handles RTL text detection.
2. `_apply_custom_format_tags(text)` — Translates n8n-specific formatting tags (`[BOLD]`, `[SUBTITLE]`, `[TABLE_START]...[TABLE_END]`, etc.) into Markdown.
3. `_normalize_table_format(text)` — Detects and normalizes pipe-delimited tables into proper Markdown table syntax.
4. `generate_pdf_from_html(html_content, base_url, student_name)` — Launches Playwright Chromium headless, sets viewport to A4 printable size (602×914px), renders HTML, waits for `window.__tocReady === true` (optional TOC script), then calls `page.pdf()` with A4 format, custom header/footer templates (student name, page number), and standard margins.

### 5.3 `routes/reports.py` — Report Business Logic

Key utility functions:
- `_build_pdf_sections(report, content, request)` — Assembles ordered section list following `major.reportSections` order, resolves images per section (top/middle/bottom positions), handles middle-image content splitting.
- `_resolve_cover_logos(content, report, request)` — Resolves up to 4 logos for the PDF cover page from `__cover.logos` in content, or falls back to college/industry logos.
- `_resolve_layout_settings(content, report)` — Resolves header/footer text from `__cover.__layout` or report defaults.
- `_normalize_section_text(value)` — Strips dangerous HTML tags, normalizes newlines, HTML-decodes escaped content from n8n payloads.
- `_sanitize_content_map(content)` — Applies `_normalize_section_text` to all content dict values (skips `__` prefixed keys which are special control keys).
- `_detect_text_direction(text)` — Detects RTL scripts (Arabic, Hebrew, Urdu, etc.) based on Unicode character ratios.

### 5.4 `routes/admin.py` — Admin Domain Logic

Key helpers:
- `_log_audit(admin_user, action, target_type, target_id, details)` — Writes to AuditLog. Never raises.
- `admin_required` decorator — Chains `token_required` + role check.
- `_normalize_major_payload(data)` — Validates and normalizes all major creation/update fields including complex nested `reportSections` and `reportPolicy`.
- `_filter_major_docs(docs, degree_id, department_doc)` — Filters majors by degree+department with backward-compatibility fallback for legacy majors without a department.
- `_resolve_public_base_url(request)` — Chooses the best base URL for PDF rendering: prefers `request.host_url` unless it's localhost, then falls back to `BACKEND_URL` from env.
- `_build_date_range_filter(from_value, to_value)` — Converts local date strings to UTC-naive `$gte`/`$lte` filters, accounting for IST timezone offset.
- Merge endpoints (`/universities/merge`, `/colleges/merge`, `/industries/merge`) — Re-point all related User, Report, and College records to the target ID, then delete the source.

### 5.5 `routes/student.py` — Student Domain Logic

- Approval visibility: `_is_visible_to_student(doc, current_user)` — returns True if the entity has `approvalStatus == 'approved'` OR if the student themselves created it. This lets students see their own pending submissions.
- `_is_profile_complete(user)` — Returns True only when name, college, university, degree, major, and industry are all set. Recalculated and saved on every profile update.
- `_serialize_user_industry_profile(user)` — Returns the effective industry profile: if `industryProfileCustomized = True`, uses user's own overrides; otherwise uses the master Industry document fields.
- `_filter_major_docs()` — Same logic as admin version but uses `_doc_id()` helper instead of `_obj_id()`.
- Student academic master-data creation endpoints exist for all three dependent entities:
  - `POST /api/student/degrees`
  - `POST /api/student/departments`
  - `POST /api/student/majors`
  Each creates records as `approvalStatus='pending'` for admin review.

### 5.5.1 `templates/student/profile.html` — Creatable Academic Selects

- Degree, Department, and Major use a custom vanilla JS "Creatable Select" combobox pattern (no external UI library).
- Each field is implemented as:
  - visible text input for filter/search
  - hidden input storing selected `_id` used in profile save payload
  - custom `<ul>` dropdown with filtered items and a dynamic `Create "..."` row when no exact match exists.
- Selecting existing options stores the corresponding `_id` immediately.
- Clicking `Create "..."` calls the student create API instantly and then auto-selects the returned entity:
  - Degree create → `POST /api/student/degrees`
  - Department create → `POST /api/student/departments` (requires selected degree)
  - Major create → `POST /api/student/majors` (requires selected degree, optional department)
- Dependency behavior:
  - Degree selection refreshes Department and Major lists.
  - Department selection refreshes Major list.

### 5.5.2 `templates/student/create_report.html` — Master-Driven Create Flow

- The create page is built around a low-effort academic sequence using master data:
  - `Degree` (master list from `/api/student/degrees`)
  - `Department` (filtered by selected degree via `/api/student/departments?degree=...`)
  - `Major` (filtered by degree + optional department via `/api/student/majors/<degree_id>?department=...`)
- Profile values (degree/department/major) are pre-selected when available, but students can change selections before generation.
- Project title input follows a hybrid model:
  - loads preset titles from `/api/student/project-titles?major=<id>` (managed by Super Admin),
  - allows custom typed title override if the preset list does not match student preference.
- The create payload includes additional context from profile where available:
  - `academicDepartment`, `semester`, `enrollmentNumber`, `supervisorName`, `supervisorContact`, keyword metadata, and skills.
- Work description supports keyword-assisted generation but can still generate when no keywords are selected by building a fallback brief description from entered internship details.
- Right sidebar summary on create page now surfaces key profile fields used by generation:
  - college, industry, semester, enrollment number, supervisor.

### 5.6 `routes/auth.py` — Authentication Module

- `generate_token(user_id, role)` — Creates HS256 JWT with 7-day expiry.
- `token_required` — Extracts Bearer token from `Authorization` header (or `?token=` / `?access_token=` query params). Looks up `User.objects(id=data['userId'])`. Returns 401 on missing/expired/invalid token.
- `_send_reset_otp_email()` — Sends OTP email via SMTP (STARTTLS or SSL based on `SMTP_USE_SSL`).
- OTP security: bcrypt-hashed, 10-minute expiry, max 5 attempts before self-invalidation.

### 5.7 `routes/bulk_import.py` — Bulk Data Import

Supports CSV and XLSX. Header aliasing: a `HEADER_ALIASES` dict maps human-readable column names to internal field names. Import handlers use `_find_by_normalized_name()` to deduplicate (case-insensitive, whitespace-normalized). For colleges, if the university doesn't exist, it is auto-created from additional columns in the same row.

### 5.8 Report Section Cascade (Hierarchical Templates)

Three-level resolution: **Major** → (if `useLevelAboveDefault=True`) → **College** → (if `useUniversityDefault=True`) → **University**.

When a Major's `reportSections` array in the `Major` document is non-empty (and there's a direct `MajorReportTemplate` with custom sections), those take priority. Otherwise the cascade applies. The endpoint `GET /api/admin/majors/<id>/effective-report-sections` computes the resolved set and returns `source: 'major_custom' | 'college_custom' | 'university_default' | 'none'`.

---

## 6. AI Developer Guide — CRITICAL SECTION

### 6.1 Code Conventions

**Python Style:**
- PEP 8 with no strict line-length enforcement; 4-space indentation.
- All public route functions are decorated with `@blueprint.route(...)` directly before `@token_required` or `@admin_required`.
- Route functions that handle both student and admin contexts check ownership: `if str(r.user.id) != str(current_user.id) and current_user.role != 'admin': return 403`.
- Serializer functions are named `_serialize_<entity>(doc)` and return plain Python dicts. They are defined at the top of each route file.
- Helper functions are named with leading underscore: `_normalize_xxx`, `_resolve_xxx`, `_build_xxx`, `_serialize_xxx`.
- `getattr(doc, 'field', default)` is the safe pattern for accessing optional fields that may not exist on older documents (due to `strict=False` on all models).

**Error Handling:**
- All route handlers return `jsonify({'message': '...'})` with appropriate HTTP status codes.
- 400 — validation/missing fields
- 401 — unauthorized (bad/missing token)
- 403 — forbidden (wrong role or not owner)
- 404 — document not found
- 409 — conflict (e.g., duplicate email)
- 500/503 — server/SMTP errors
- Audit logging in `_log_audit()` wraps in try/except and never raises.
- ORM operations that might fail are caught and logged, not re-raised, in most places.

**Naming Conventions:**
- Model field names: `camelCase` (e.g., `isActive`, `createdAt`, `villageCityName`, `rollNumber`).
- Python local variables: `snake_case`.
- URL paths: `kebab-case` (e.g., `/api/admin/work-keywords`).
- Blueprint names: `auth_bp`, `admin_bp`, `student_bp`, `reports_bp`, `upload_bp`, `bulk_import_bp`, `internship_types_bp`, `pages_bp`.

**Response Structure:**
- List endpoints return a plain JSON array `[{...}, {...}]`.
- Single-resource endpoints return a flat JSON object with `_id` as the identifier key.
- Error responses always return `{'message': 'Human-readable error'}`.
- Success mutation responses return `{'message': 'Deleted'}` or the updated document.

### 6.2 Modification Rules

#### How to Add a New Data Entity (Model + CRUD)

1. **Create `models/<entity>.py`** — Extend `Document`, set `meta = {'collection': '<collection_name>', 'strict': False}`, define fields using `StringField`, `BooleanField`, `IntField`, `ReferenceField`, etc. from `mongoengine` (which resolves to the custom shim).
2. **Register in `models/__init__.py`** — Add import and add to `__all__`.
3. **Add serializer** — Add `_serialize_<entity>(doc)` function in the relevant route file (admin or student). Always include `'_id': _obj_id(doc)` or `str(doc.id)`.
4. **Add routes** — Create CRUD endpoints (GET list, POST create, GET single, PUT update, DELETE) in `routes/admin.py` or create a new blueprint file.
5. **If new blueprint** — Register it in `app.py`: `from routes.newmodule import new_bp; app.register_blueprint(new_bp, url_prefix='/api/...')`.
6. **Add admin page route** — Add the HTML route in `routes/pages.py` under `admin_pages` section.
7. **Create admin template** — Create `templates/admin/manage_<entity>.html` extending `admin/layout.html`.

#### How to Add a New Report Section Field

1. Report sections are defined in `major.reportSections` as a list of embedded `ReportSection` objects (`key`, `title`, `description`).
2. The section key must be unique within a major. It becomes the dictionary key in `generatedContent`, `editedContent`, `generatedTitles`, and `sectionImages`.
3. Edit the Major via admin panel (or API `PUT /api/admin/majors/<id>` with `reportSections` array).
4. The n8n webhook payload includes the sections list under `reportConfig.sections`. n8n uses this to generate content for each section key.
5. The PDF template (`pdf_template.html`) iterates `sections` variable built by `_build_pdf_sections()` — no template changes needed for new sections.

#### How to Modify the PDF Output

- The template is `templates/pdf_template.html`. It receives: `report`, `college`, `university`, `industry`, `cover_logos`, `layout_settings`, `sections`.
- Each section dict has: `key`, `title`, `content` (safe HTML), `content_before`, `content_after` (split for middle images), `images_top`, `images_middle`, `images_bottom`, `direction` ('ltr'|'rtl'), `is_rtl`.
- The `__cover` special key in `generatedContent` can carry `logoCount` and `logos` array for cover page customization.
- The `__layout` special key carries `showHeader`, `showFooter`, `headerLeft`, `headerRight`, `footerText`.
- PDF margins: top=30mm, bottom=25.4mm, left=25.4mm, right=25.4mm. Format: A4. Viewport: 602×914px.

#### How to Add a New Admin Route

```python
# In routes/admin.py:
@admin_bp.route('/my-entity', methods=['GET'])
@admin_required
def get_my_entities(current_user):
    docs = MyEntity.objects().order_by('name')
    return jsonify([_serialize_my_entity(d) for d in docs])
```

- Always decorate with `@admin_required` (not raw `@token_required`).
- `current_user` is injected as the first argument after both decorators.
- For write operations, call `_log_audit(current_user, 'action_name', 'target_type', doc.id, {...})`.

#### How to Add a New Student Route

```python
# In routes/student.py:
@student_bp.route('/my-resource', methods=['GET'])
@token_required
def get_resource(current_user):
    # current_user is the authenticated User document
    ...
```

#### How to Add Entity Approval Workflow

Models that need admin approval follow this pattern:
1. Student creates with `approvalStatus='pending'`.
2. Admin can approve (`approvalStatus='approved'`, `isVerified=True`, clear `rejectionReason`) or reject (`approvalStatus='rejected'`, `rejectionReason=...`).
3. Student visibility: entity is visible if `approvalStatus == 'approved'` OR `createdBy == current_user.id`.
4. Add endpoints: `PUT /api/admin/<entity>/<id>/approve` and `PUT /api/admin/<entity>/<id>/reject`.
5. In student list endpoints, use `_is_visible_to_student(doc, current_user)` pattern.

### 6.3 Security & Authentication

**DO NOT break these patterns:**

1. **JWT Verification** — Always use `@token_required` or `@admin_required`. Never access `request.headers` for auth manually in a route — the decorator handles this.

2. **Admin-only routes** — Use `@admin_required`, never just `@token_required` with a manual role check in the function body (the decorator wraps `token_required`, so the signature is the same: `def handler(current_user, ...)`).

3. **n8n Webhook Security** — The `PUT /api/reports/<id>/generated` endpoint (no JWT) MUST verify `X-Callback-Secret` using `secrets.compare_digest()` when `N8N_CALLBACK_SECRET` is configured. Never use `==` for secret comparison.

4. **Ownership Check** — Any route that accesses a specific User's Report, Payment, or profile must check: `str(r.user.id) != str(current_user.id) and current_user.role != 'admin'`.

5. **Password Security** — Passwords are bcrypt-hashed with cost 12. Never store plaintext. Use `user.set_password()` and `user.check_password()`.

6. **OTP Security** — OTPs are bcrypt-hashed before storage. Max 5 attempts, 10-minute expiry. The same generic message is returned whether email exists or not (anti-enumeration).

7. **File Upload Security** — Use `secure_filename()` from Werkzeug. Validate file extension against allowlist. Validate MIME type starts with `image/`. Check file size ≤ 5MB. Never allow path traversal.

8. **HTML Content Sanitization** — All text from n8n callbacks goes through `_normalize_section_text()` which strips dangerous tags (`<script>`, `<style>`, `<iframe>`, etc.) and allows only a safe subset of formatting tags.

9. **JWT Secret** — Must be set via `JWT_SECRET` env var. If missing, `generate_token()` raises `RuntimeError`. Never hardcode a secret.

10. **SMTP Credentials** — Configured entirely via `.env`. If `SMTP_HOST` or `SMTP_FROM_EMAIL` is missing, email functions raise `RuntimeError` with a clear message.

### 6.4 ORM-Specific Rules for This Project

**Critical rules when writing DB queries:**

```python
# ✅ CORRECT — Filter booleans in Python, not in ORM query
docs = [u for u in User.objects(role='student') if getattr(u, 'isActive', True)]

# ❌ WRONG — BooleanField filter is unreliable with SQLite backend
docs = User.objects(role='student', isActive=True)

# ✅ CORRECT — Access ReferenceField safely with getattr
name = getattr(getattr(user, 'college', None), 'name', '')

# ❌ WRONG — Direct access raises AttributeError if reference is None
name = user.college.name

# ✅ CORRECT — Get document ID safely
doc_id = str(doc.id)
# or use the helper: _obj_id(doc) or _doc_id(doc) (same pattern in each file)

# ✅ CORRECT — After model.save(), the returned object is the same instance
doc = MyModel(name='x')
doc.save()
str(doc.id)  # valid

# ✅ CORRECT — Case-insensitive name deduplication uses normalized comparison
existing = next((d for d in Model.objects() if 
    re.sub(r'\s+', ' ', str(getattr(d, 'name', '')).casefold()) == 
    re.sub(r'\s+', ' ', name.casefold())), None)
```

**QuerySet behaviors:**
- `.first()` returns `None` if no match (never raises).
- `.count()` uses SQL pushdown when possible; falls back to Python.
- `.delete()` returns count of deleted rows.
- `.update(set__field=value)` iterates, updates, and saves each doc individually.
- Sorting is case-insensitive in the SQL pushdown path (`LOWER(CAST(...) AS TEXT)`).

### 6.5 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | **Yes** | HS256 signing secret for JWTs |
| `SQLITE_PATH` | No | Path to `app.db`. Default: `<app_root>/data/app.db` |
| `PORT` | No | Flask port. Default: 5000 |
| `N8N_WEBHOOK_URL` | Yes (for generation) | Full URL to n8n webhook for AI report generation |
| `N8N_CALLBACK_SECRET` | Yes (for security) | Shared secret sent in `X-Callback-Secret` header |
| `BACKEND_URL` | Yes (for PDF/ngrok) | Public base URL used for PDF image resolution |
| `REPORT_DESCRIPTION_MODE` | No | `hybrid` (default) / `legacy` / `keywords_only` |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID for Google Sign-In button |
| `SMTP_HOST` | For email | SMTP server hostname |
| `SMTP_PORT` | For email | Default 587 |
| `SMTP_USER` | For email | SMTP username |
| `SMTP_PASS` | For email | SMTP password |
| `SMTP_FROM_EMAIL` | For email | Sender email address |
| `SMTP_FROM_NAME` | No | Sender display name. Default: ReportGen Support |
| `SMTP_USE_SSL` | No | `true` for SSL, default false (STARTTLS) |
| `FORGOT_PASSWORD_OTP_DEBUG` | No | `true` to return OTP in response body (dev only!) |
| `UPLOAD_DIR` | No | Legacy, not used in production routes |

### 6.6 Common Gotchas & Bug Patterns

1. **Reference fields are lazy-loaded** — Accessing `report.user.name` triggers a DB lookup. Do not call this in a tight loop without checking for None. Use `getattr(report.user, 'name', '')` pattern.

2. **`strict=False` on all models** — Extra fields in stored JSON are preserved and accessible via `doc._data['unknown_field']`. This is intentional for forward-compatibility.

3. **`app.db-wal` and `app.db-shm` files** — WAL mode creates these alongside the main `.db` file. They are all part of the same database and should not be deleted individually.

4. **`descriptionSource` and `selectedWorkKeywords`** — These are dynamic fields set via `report.descriptionSource = value` (not declared as typed fields in `report.py`). They are stored because `strict=False` allows arbitrary extra fields. When reading them, use `getattr(r, 'descriptionSource', '')`.

5. **`editedContent` is initialized from `generatedContent`** — When the n8n callback fires, it sets BOTH `generatedContent` and `editedContent` to the same normalized content. Students edit `editedContent`. PDF download always uses `editedContent or generatedContent`.

6. **`_obj_id()` vs `_doc_id()`** — Both are defined locally in each route file as the same helper pattern. They exist as separate functions in `admin.py` and `student.py` due to module isolation. They do the same thing: safely extract `str(doc.id)` or `''`.

7. **Approval status backward compatibility** — Older records may have `approvalStatus = null` or `''`. Always use `_normalized_approval_status(doc)` or the pattern: `str(getattr(doc, 'approvalStatus', '') or '').strip().lower() or 'approved'`.

8. **College template `useUniversityDefault`** vs Major template `useLevelAboveDefault`** — Different flag names for the same concept at different levels. College uses `useUniversityDefault`, Major uses `useLevelAboveDefault`.

9. **`report.sectionImages`** — Stored as a `DictField`. Each key is a `section_key`, each value is a list of image dicts: `{url, filename, position ('top'|'middle'|'bottom'), caption, widthPercent}`. When modifying, always do `images = dict(r.sectionImages or {}); ...; r.sectionImages = images; r.save()`.

10. **Image URL resolution in PDFs** — `_normalize_asset_url(url, request)` ensures relative `/static/...` URLs are converted to absolute using the current request's host. This avoids stale `BACKEND_URL` env values breaking image rendering.
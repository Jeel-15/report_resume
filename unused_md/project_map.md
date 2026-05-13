# PROJECT MAP — ReportGen (Flask + SQLite Internship Report Platform)

> **Read this first before touching any file.**
> This document is the single source of truth for understanding the codebase.
> Every AI or developer working on this project MUST start here.

---

## 1. What This Project Is

**ReportGen** is a Flask web application that lets college students generate, edit, and download AI-written internship reports as PDFs.

Key facts:
- **Backend**: Python / Flask
- **Database**: SQLite — but accessed through a **custom MongoEngine-compatible ORM** written from scratch (`mongoengine.py`). All models use MongoEngine-style syntax (`Document`, `StringField`, `ReferenceField`, etc.) but store data in a single SQLite table.
- **AI generation**: Outsourced to an external n8n workflow (webhook). The app sends a payload → n8n generates content → n8n calls back a `/generated` endpoint on this app.
- **PDF generation**: Playwright (headless Chromium) renders an HTML template to PDF.
- **Auth**: JWT tokens (stored in browser `localStorage`). Rate-limited login. Google Sign-In optional.
- **Two roles**: `student` and `admin`.

---

## 2. The Critical Architecture Fact (Read This Carefully)

The models in `models/` import from `mongoengine` — but `mongoengine` here is **NOT the real PyPI mongoengine package**. It is the local file `mongoengine.py` at the project root.

```
mongoengine.py          ← CUSTOM file. Implements Document, StringField, ReferenceField,
                           QuerySet, etc. using SQLite as storage backend.
models/user.py          ← imports from mongoengine (resolves to mongoengine.py above)
models/report.py        ← same
... all models ...      ← same
```

**SQLite storage schema** (single table for ALL collections):
```sql
__documents (
    collection TEXT,   -- e.g. "users", "reports", "majors"
    id         TEXT,   -- 24-char hex string (like a MongoDB ObjectId)
    data       TEXT,   -- JSON blob of the document fields
    updated_at TEXT    -- ISO timestamp
    PRIMARY KEY (collection, id)
)
```

ReferenceField values are stored as plain string IDs. When accessed on a Document instance, they are lazy-loaded by fetching the referenced document from SQLite.

---

## 3. Directory Structure with Purpose

```
project_root/
│
├── app.py                         # Flask app factory + blueprint registration
├── mongoengine.py                 # CUSTOM ORM — SQLite backend, MongoEngine API surface
├── migrate_mongo_to_sqlite.py     # One-time migration tool: MongoDB → SQLite
├── test_db.py                     # Manual DB inspection/test script
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (see Section 6)
│
├── models/                        # Data models (use mongoengine.py ORM)
│   ├── user.py                    # User (students + admins)
│   ├── report.py                  # Internship report document
│   ├── payment.py                 # Payment record
│   ├── service.py                 # Purchasable service (report generation, etc.)
│   ├── degree.py                  # Degree type (e.g. B.Tech, BCA)
│   ├── major.py                   # Major/subject (linked to Degree); contains AI config
│   ├── college.py                 # College (linked to University)
│   ├── university.py              # University
│   ├── industry.py                # Company/industry where student interned
│   ├── project_title.py            # Project title bank mapped to Major/Degree
│   ├── internship_type.py         # Internship category type (admin-created)
│   └── __init__.py
│
├── routes/                        # Flask Blueprints (API + page rendering)
│   ├── auth.py                    # /api/auth/* — login, register, Google login, JWT, OTP
│   ├── reports.py                 # /api/reports/* — CRUD, PDF download, image upload
│   ├── student.py                 # /api/student/* — profile, degrees/colleges/etc., reports
│   ├── admin.py                   # /api/admin/* — manage all entities, stats, payments
│   ├── bulk_import.py             # /api/admin/bulk-import/* — XLSX/CSV templates + import handlers
│   ├── upload.py                  # /api/upload/* — college/industry logo upload
│   ├── internship_types.py        # /api/internship-types/* — CRUD for InternshipType
│   ├── pages.py                   # HTML page routes (no /api prefix) — renders templates
│   └── __init__.py
│
├── utils/
│   └── pdf.py                     # Markdown→HTML converter + Playwright PDF generator
│
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Shared base layout
│   ├── landing.html               # Public landing page
│   ├── login.html / register.html / forgot_password.html / logout.html
│   ├── pdf_template.html          # THE PDF layout — rendered by Playwright
│   ├── partials/                  # Shared HTML fragments (navbar, footer, admin theme)
│   ├── admin/                     # Admin dashboard pages (dashboard, manage_* pages, bulk import)
│   ├── student/                   # Student pages (dashboard, profile, create_report, report_view)
│
├── static/
│   ├── css/                       # Global styles (design-system, animations, navbar, etc.)
│   ├── js/                        # Global JS (animations, navbar)
│   ├── images/                    # Static images (SVG fallback photo)
│   └── uploads/
│       └── report_images/
│           └── <report_id>/
│               └── <section_key>/
│                   └── <uuid>.jpg  # Section images uploaded by student
│
├── data/
│   ├── app.db                     # The SQLite database (live)
│   └── app_backup_before_full_migration_20260415_094557.db  # Backup before migration
│
├── uploads/                       # Logo uploads (college/industry logos)
│   ├── colleges/<uuid>.png
│   └── industries/<uuid>.png
│
└── animation/                     # Standalone hero animation prototype (hero.html/css/js)
```

---

## 4. Data Models

### User
```
email (unique), password (bcrypt), role (student|admin), isActive
name, villageCityName, tehsil, district, state, phone, whatsapp
gender, semester, department
university → University, college → College, degree → Degree, major → Major
rollNumber, enrollmentNumber
industry → Industry, supervisorName, supervisorContact
profileCompleted (bool)
resetOtpHash, resetOtpExpiresAt, resetOtpAttemptCount  ← forgot-password OTP state
```

### Report
```
user → User
degree → Degree, major → Major, college → College, university → University, industry → Industry

# Cover page fields
projectTitle (required), internshipTitle, academicYear, rollNumber, studentEmail

# Internship details
supervisorName, supervisorContact, duration, startDate, endDate, positionTitle

# Input for AI
briefDescription (required), keySkills

# AI output
reportLanguage, generatedContent (dict), generatedTitles (dict), generatedUiLabels (dict)
editedContent (dict)  ← student edits stored here; this is what gets PDFed
sectionImages (dict)  ← { "sectionKey": [ {url, filename, position, caption, widthPercent} ] }

status: pending → generating → generated → edited → final | error
isPaid, payment → Payment, downloadCount
```

### Major (most complex model — drives AI behavior)
```
degree → Degree, name
reportLanguage, reportContentType, aiPromptContext
reportPolicy (embedded):
    strictLanguageOnly, allowedLanguages, generationInstruction
    uiLabels (dict), sectionTitleMap (dict), contentFeatures (list)
    imagesRequired (bool)
reportSections (list of embedded):
    key, title, description   ← defines report structure sent to n8n
employmentOpportunities (list of embedded)
```

### Payment
```
user → User, service (dynamic ref), report → Report
amount, gstAmount, totalAmount
status: pending | completed | failed | refunded
paymentMethod, transactionId
```

### Service
```
name (unique), type (resume|task|report)
price, gstIncluded, gstPercent, freeLimit
degreePricing (list of embedded): { degree → Degree, price }
description, isActive
```

### University / College / Industry
All have: `name, villageCityName, tehsil, district, state, website, createdBy, isVerified, isActive`
College also has: `university → University, logo, approvalStatus, rejectionReason`
Industry also has: `logo, gstNumber, industryDetails, industryType, industrySubType, keyActivities, approvalStatus, rejectionReason`

Student-created universities, colleges, and industries are saved with `approvalStatus='pending'` and remain visible to the creating student.

### ProjectTitle
```
title, major → Major, degree → Degree, isActive, createdBy → User
```

### InternshipType
```
name, description, aiPromptContext, icon, isActive, createdBy → User
reportSections (list of embedded): key, title, description
```

---

## 5. API Routes Reference

### Auth — `/api/auth`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | No | Email+password login → JWT token |
| POST | `/register` | No | Create student account |
| POST | `/google-login` | No | Google OAuth ID token → JWT token |
| POST | `/logout` | No | Client clears localStorage (server stateless) |
| GET | `/me` | JWT | Get current user profile |
| POST | `/forgot-password/request-otp` | No | Send 6-digit OTP to email |
| POST | `/forgot-password/verify-otp` | No | Verify OTP + set new password |

### Reports — `/api/reports`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/my` | JWT | List current user's reports |
| GET | `/<id>` | JWT | Get full report (owner or admin) |
| POST | `/` | JWT | Create report + trigger n8n generation |
| PUT | `/<id>/content` | JWT | Save student edits to `editedContent` |
| GET | `/<id>/pdf` | JWT | Download PDF (uses editedContent if present) |
| POST | `/<id>/pdf-preview` | JWT | Generate PDF preview with unsaved edits |
| PUT | `/<id>/generated` | Secret | **n8n callback** — save AI-generated content |
| POST | `/<id>/images/<section>` | JWT | Upload section image |
| PUT | `/<id>/images/<section>/<file>` | JWT | Update image metadata (position/caption/width) |
| DELETE | `/<id>/images/<section>/<file>` | JWT | Delete section image |
| DELETE | `/<id>` | JWT | Delete report |

### Student — `/api/student`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/degrees` | JWT | Active degrees list |
| GET | `/majors` | JWT | All active majors |
| GET | `/majors/<degree_id>` | JWT | Majors filtered by degree |
| GET | `/major/<major_id>` | JWT | Single major |
| GET | `/universities?q=` | JWT | Search universities (approved + own pending, max 50) |
| POST | `/universities` | JWT | Create university if not exists (pending) |
| GET | `/colleges?q=&university=` | JWT | Search colleges (approved + own pending) |
| POST | `/colleges` | JWT | Create college if not exists (pending) |
| GET | `/industries?q=` | JWT | Search industries (approved + own pending) |
| POST | `/industries` | JWT | Create industry if not exists (pending) |
| GET | `/project-titles?major=` | JWT | Active project titles for selected major |
| GET | `/profile` | JWT | Full profile |
| PUT | `/profile/personal` | JWT | Update name/address/phone + gender/semester/department |
| PUT | `/profile/college` | JWT | Update university/college/degree/major/roll number |
| PUT | `/profile/industry` | JWT | Update industry/supervisor |
| GET | `/services` | JWT | Active services list |
| GET | `/reports` | JWT | Own reports list |
| GET | `/reports/<id>` | JWT | Own report detail |
| PUT | `/reports/<id>/content` | JWT | Save edits |
| POST | `/reports/<id>/pdf-preview` | JWT | PDF preview |
| POST/PUT/DELETE | `/reports/<id>/images/<section>/<file>` | JWT | Image management |

### Bulk Import — `/api/admin/bulk-import`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/template/<entity>` | Admin | Download XLSX template for universities, colleges, industries, or project titles |
| POST | `/<entity>` | Admin | Import rows from CSV/XLSX and auto-create missing parent universities when needed |

### Admin — `/api/admin`
All routes require JWT + `role == 'admin'`.
| Resource | Operations |
|----------|-----------|
| `/stats` | GET dashboard counts |
| `/degrees` | GET (search), POST, PUT `/<id>`, DELETE `/<id>` |
| `/majors` | GET (search/filter), GET `/<id>`, POST, PUT `/<id>`, DELETE `/<id>` |
| `/universities` | GET, PUT `/<id>`, DELETE `/<id>`, POST `/merge` |
| `/colleges` | GET, PUT `/<id>`, DELETE `/<id>`, POST `/merge` |
| `/industries` | GET, PUT `/<id>`, DELETE `/<id>`, POST `/merge`, PUT `/<id>/approve`, PUT `/<id>/reject` |
| `/project-titles` | GET, POST, PUT `/<id>`, DELETE `/<id>` |
| `/users` | GET (search), GET `/<id>`, PUT `/<id>/toggle`, DELETE `/<id>` |
| `/services` | GET, POST, PUT `/<id>`, DELETE `/<id>` |
| `/payments` | GET (date filter) |
| `/reports` | GET all, DELETE `/<id>` |

### Internship Types — `/api/internship-types`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | Active types |
| GET | `/all` | Admin | All types |
| GET | `/<id>` | JWT | Single type |
| POST | `/` | Admin | Create |
| PUT | `/<id>` | Admin | Update |
| DELETE | `/<id>` | Admin | Delete |

### Upload — `/api/upload`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/logo/college` | JWT | Upload college logo → `/uploads/colleges/<uuid>.png` |
| POST | `/logo/industry` | JWT | Upload industry logo → `/uploads/industries/<uuid>.png` |

### Pages — HTML (no `/api` prefix)
`/`, `/login`, `/register`, `/forgot-password`, `/logout`
`/student/dashboard`, `/student/profile`, `/student/create`, `/student/report/<id>`
`/admin/dashboard`, `/admin/majors`, `/admin/users`, `/admin/degrees`, `/admin/universities`
`/admin/colleges`, `/admin/industries`, `/admin/services`, `/admin/payments`
`/admin/bulk-import`
`/admin/reports`, `/admin/report/<id>`, `/admin/types`, `/admin/settings`, `/admin/notifications`

---

## 6. Report Generation Flow (The Core Workflow)

```
Student fills form → POST /api/reports/
      ↓
Flask creates Report (status="generating")
      ↓
Flask sends POST to N8N_WEBHOOK_URL with full payload (student info, college, industry,
academic details, internship details, reportConfig: {language, sections, AI context})
      ↓
n8n runs AI workflow (up to 120s timeout — does NOT fail on timeout, stays "generating")
      ↓
n8n calls back: PUT /api/reports/<id>/generated  (authenticated via X-Callback-Secret header)
Payload: { generatedContent: {sectionKey: text}, generatedTitles: {sectionKey: title},
           generatedUiLabels: {...} }
      ↓
Flask saves generatedContent + editedContent (copy) → status="generated"
      ↓
Student sees report, edits sections inline → PUT /api/reports/<id>/content
(saves to editedContent, status="edited")
      ↓
Student downloads PDF → GET /api/reports/<id>/pdf
Flask renders pdf_template.html with Playwright → returns PDF bytes
```

---

## 7. PDF Generation Details

File: `utils/pdf.py`

Pipeline:
1. `_md_to_html(text)` — converts section content (markdown + custom tags) to HTML
2. Custom tags supported from n8n AI output:
   - `[BOLD]...[/BOLD]` → `**...**`
   - `[SUBTITLE]...[/SUBTITLE]` → bold paragraph
   - `[SUBPOINT]...[/SUBPOINT]` → nested bullet
   - `[TABLE_START]...[TABLE_END]` → markdown table
   - `[BULLET_START]...[BULLET_END]` → unordered list
   - `[NUMBER_START]...[NUMBER_END]` → ordered list
3. `generate_pdf_from_html(html, base_url, student_name)` — uses Playwright/Chromium
   - Viewport: 602×914px (A4 printable area at 96dpi)
   - Margins: top 30mm, bottom 25.4mm, left/right 25.4mm
   - Custom header: student name | project title
   - Custom footer: student name + page number + "Plagiarism check below 15%"

Template: `templates/pdf_template.html`
Receives: `report`, `college`, `university`, `industry`, `cover_logos`, `layout_settings`, `sections`

Section images support 3 positions: `top`, `middle` (splits content 50/50), `bottom`

Text direction auto-detected (RTL for Arabic/Urdu/Hebrew if >20% RTL chars).

---

## 8. Authentication System

File: `routes/auth.py`

- **JWT**: HS256, 7-day expiry, payload `{userId, role, exp, iat}`
- **Token source**: `Authorization: Bearer <token>` header OR `?token=` query param
- **Decorator**: `@token_required` — injects `current_user` (User object) into route
- **Admin decorator**: `@admin_required` — wraps `@token_required` + checks `role == 'admin'`
- **Rate limits**: login 10/min, google-login 20/min, OTP request 5/15min
- **Password rules**: ≥8 chars, ≥1 uppercase, ≥1 number
- **Forgot password OTP**: 6-digit, bcrypt-hashed, 10-min expiry, max 5 attempts
- **Google login**: verifies `google.oauth2.id_token`, auto-creates student account if new
- **Logout**: Server stateless — client clears localStorage

---

## 9. The Custom ORM (`mongoengine.py`)

This file replaces the real mongoengine package. It provides:

**Field types**: `StringField`, `BooleanField`, `IntField`, `FloatField`, `DictField`,
`DateTimeField`, `ListField`, `ReferenceField`, `EmbeddedDocumentField`, `EmbeddedDocumentListField`, `DynamicField`

**Document classes**: `EmbeddedDocument`, `Document`

**QuerySet API** (all data loaded into memory then filtered in Python):
```python
Model.objects(**filters)           # filter
Model.objects(id=x).first()        # fetch one
Model.objects.count()              # count
Model.objects(x=y).order_by('name')
Model.objects(x=y).delete()
Model.objects(x=y).update(set__field=value)
```

**Filter operators**: `eq`, `in`, `icontains`, `iexact`, `__raw__` ($or, $regex, $gte, $lte)

**Important limitations**:
- No transactions
- No real indexes (unique constraints enforced in Python before save)
- All queries load ALL documents for the collection into memory and filter in Python — **do not store millions of records**
- `ReferenceField` resolves lazily on first attribute access (cached per instance in `_ref_cache`)
- IDs are 24-char hex strings (like MongoDB ObjectIds), generated with `secrets.token_hex(12)`

**Storage**: Single SQLite table `__documents`, JSON-serialized per document.

---

## 10. Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No (default 5000) | Flask server port |
| `JWT_SECRET` | YES | Secret for signing JWT tokens |
| `SQLITE_PATH` | No | Path to SQLite DB (default: `data/app.db`) |
| `N8N_WEBHOOK_URL` | YES for AI gen | Full URL of n8n webhook endpoint |
| `N8N_CALLBACK_SECRET` | YES for security | Secret header value for n8n → Flask callback |
| `BACKEND_URL` | YES (prod) | Public base URL (e.g. ngrok URL) for PDF image resolution |
| `GOOGLE_CLIENT_ID` | No | Enables Google Sign-In button |
| `SMTP_HOST` | No | Email server for OTP emails |
| `SMTP_PORT` | No (default 587) | |
| `SMTP_USER` | No | |
| `SMTP_PASS` | No | |
| `SMTP_FROM_EMAIL` | No | |
| `SMTP_FROM_NAME` | No (default "ReportGen Support") | |
| `SMTP_USE_SSL` | No (default false) | Use SSL vs STARTTLS |
| `FORGOT_PASSWORD_OTP_DEBUG` | No | If `true`, returns OTP in JSON response (dev only) |
| `MONGODB_URI` | Migration only | Used only by `migrate_mongo_to_sqlite.py` |

---

## 11. How to Run

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set environment
cp .env .env.local  # edit as needed, at minimum set JWT_SECRET

# Run
python app.py
# → http://localhost:5000
```

**Data migration from MongoDB** (one-time):
```bash
python migrate_mongo_to_sqlite.py --mongo-uri mongodb://... --sqlite-path data/app.db
python migrate_mongo_to_sqlite.py --dedupe-users  # remove duplicate user rows by email
```

---

## 12. Key Rules for Modifications

1. **Never import `mongoengine` from PyPI** — the local `mongoengine.py` must always take precedence. If you add new dependencies, ensure `mongoengine` is not in `requirements.txt`.

2. **All model changes require understanding storage**: Fields are serialized to JSON. `ReferenceField` stores only the string ID. Access `user.college` triggers a DB query; access `user._data['college']` gives the raw string ID.

3. **n8n callback shape**: The `PUT /api/reports/<id>/generated` endpoint accepts `generatedContent` as either:
   - A flat dict: `{ "sectionKey": "text content" }`
   - An object dict: `{ "sectionKey": { "sectionContent": "...", "sectionTitle": "..." } }`
   Never pass `[object Object]` stringified values — the endpoint explicitly rejects these.

4. **PDF image URLs**: Always resolved relative to `request.host_url` at render time — never hardcoded. The `BACKEND_URL` env var is used as fallback when the request is from localhost.

5. **Profile completion check**: `profileCompleted` is recalculated on every profile update by `_is_profile_complete()` — it requires: name, college, university, degree, major, industry all to be set.

6. **Admin merge endpoints** for universities/colleges/industries: These reassign all references in users, reports, and related collections before deleting the source document. Always use merge instead of delete when duplicates exist.

7. **Section content sanitization**: All content going into or coming out of the DB is passed through `_normalize_section_text()` / `_sanitize_content_map()`. These strip dangerous HTML tags, unescape double-encoded entities, and normalize newlines. The `__cover` and `__layout` keys in `generatedContent` are special metadata keys (start with `__`) and are NOT sanitized.

8. **Industry approval flow**: Student-created industries are stored with `approvalStatus='pending'`. Admin can approve/reject them and the UI should show the current status.

9. **Project title bank**: Project titles are stored separately by major and can be fetched for the student create-report flow. If no titles exist, the page should fall back to free text.

10. **Student profile draft flow**: The Add University / Add College / Add Industry buttons on the student profile page are draft-only UI actions. Final persistence happens on the section Save button, which also creates any missing related university/college/industry records.

---

## 13. Files to Ignore / Not Modify

| File/Path | Reason |
|-----------|--------|
| `data/app.db` | Live database — never edit manually |
| `data/app_backup_*.db` | Migration backup |
| `data/duplicate_users_backup.json` | Migration artifact |
| `static/uploads/` | User-uploaded files, report images, and playable video-guide uploads |
| `uploads/` | Legacy compatibility path for older logo uploads |
| `**/__pycache__/` | Python bytecode |
| `templates/landing.html.bak` | Old backup |
| `animation/` | Prototype/sandbox only |
## 14. Current Live Product Map

### Public / guest
- `/` is the public landing page and is the best place for first-time visitors.
- `/login`, `/register`, `/forgot-password`, and `/logout` are public auth pages.
- Guests should not see `/student/dashboard`; that page is a private reports workspace.
- If we want to attract new users before signup, the right move is to add teaser content to `templates/landing.html`, not to open the student dashboard publicly.

### Logged-in student
- `/student/dashboard` is the main reports page.
- `/student/profile` is for profile completion and edits.
- `/student/create` starts a new report.
- `/student/report/<id>` is the report editor/viewer.
- The dashboard now includes a "How-To Videos" section that shows active guides after login.

### Admin
- `/admin/dashboard` and the `manage_*` pages are the admin workspace.
- Admin can manage users, reports, colleges, universities, industries, services, payments, bulk imports, audit logs, and video guides.
- `templates/admin/manage_video_guides.html` is the admin editor for video guides.
- `templates/admin/audit_log.html` is the audit trail page.

### Video guide flow
- Admin creates guides through `/admin/video-guides`.
- `videoType = youtube` stores a YouTube URL and renders as an embed on the student dashboard.
- `videoType = upload` stores a server path like `/uploads/video_guides/<file>` and renders as an HTML5 video player.
- Uploaded files are stored under `static/uploads/video_guides/`.
- If you want a public marketing version later, reuse the landing page and show only curated teaser guides there.

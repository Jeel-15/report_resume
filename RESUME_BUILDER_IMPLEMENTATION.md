# Resume Builder Feature — 4-Phase Implementation Summary

**Status:** ✅ Complete  
**Phases:** 1 (Models + Admin) → 2 (Student APIs) → 3 (PDF Template) → 4 (Frontend)  
**Date:** May 7, 2026

---

## Phase 1: Data Models, Admin APIs & Admin UI

### Files Created

#### `models/resume.py` (NEW)
- **Purpose:** Core Resume document storing all resume sections
- **Key Classes:**
  - `ResumeEducation` — Embedded document with degreeName, collegeUniversityName, passingYear, percentageCgpa, sortOrder
  - `ResumeExperience` — Embedded with companyName, position, rawDutyKeywords (list), sortOrder
  - `ResumeProject` — Embedded with title, rawKeywords (list), sortOrder
  - `ResumeVolunteering` — Embedded with organizationName, role, duration, rawContributionKeywords (list), sortOrder
  - `ResumeCertification` — Embedded with certificationName, issuingAuthority, year, sortOrder
  - `ResumeLanguage` — Embedded with languageName, proficiency, sortOrder
  - `Resume` — Main document with:
    - Personal: fullName, address, phone, email, photoUrl
    - Career: careerObjectiveRaw, careerObjectiveEnhanced
    - Sections: education (list), experience (list), skills (list), technicalSkills (list), projects (list), volunteering (list), certifications (list), languages (list)
    - Status tracking: status (draft/generating/generated/downloaded), createdBy (FK to User), timestamps
    - Metadata: title, downloadCount

#### `models/career_objective.py` (NEW)
- **Purpose:** Store pre-defined and student-submitted career objectives with admin approval workflow
- **Key Fields:**
  - text — Career objective text
  - major — Optional FK to Major
  - approvalStatus — pending/approved/rejected
  - createdBy — FK to User (who submitted)
  - isActive — Boolean for admin soft-delete
  - Timestamps: createdAt, updatedAt

#### `models/resume_keyword.py` (NEW)
- **Purpose:** Curated keywords for resume sections, filterable by industry/major
- **Key Fields:**
  - keyword — The keyword text
  - category — skill/technical/experience/project/volunteering
  - industryType — Industry classification
  - major — Optional FK to Major
  - isActive — Boolean for soft-delete
  - Timestamps: createdAt, updatedAt

#### `models/__init__.py` (MODIFIED)
- Added exports: `Resume, ResumeEducation, ResumeExperience, ResumeProject, ResumeVolunteering, ResumeCertification, ResumeLanguage, CareerObjective, ResumeKeyword`

### Admin Routes Created

#### `routes/admin.py` (MODIFIED)

**Career Objectives Endpoints:**
- `GET /api/admin/career-objectives` — List all with pagination, filters (major, status, q)
- `POST /api/admin/career-objectives` — Create new objective
- `PUT /api/admin/career-objectives/<id>` — Update objective (text, major, status, isActive)
- `DELETE /api/admin/career-objectives/<id>` — Delete objective

**Resume Keywords Endpoints:**
- `GET /api/admin/resume-keywords` — List all with pagination, filters (category, major, industryType, q)
- `POST /api/admin/resume-keywords` — Create new keyword
- `PUT /api/admin/resume-keywords/<id>` — Update keyword
- `DELETE /api/admin/resume-keywords/<id>` — Delete keyword

**Helper Functions:**
- `_serialize_career_objective(doc)` — Returns _id, text, major, approvalStatus, createdBy, timestamps
- `_serialize_resume_keyword(doc)` — Returns _id, keyword, category, industryType, major, isActive

### Admin UI Templates Created

#### `templates/admin/manage_career_objectives.html` (NEW)
- Responsive table with columns: Text, Major, Status, Created By, Timestamps, Actions
- Filters: Major dropdown, Status dropdown, Search input
- Modal for add/edit with form fields (text, major select, approval status)
- Delete confirmation dialog
- Create button and actions (Edit, View, Delete)

#### `templates/admin/manage_resume_keywords.html` (NEW)
- Responsive table with columns: Keyword, Category, Industry, Major, Status, Actions
- Filters: Category dropdown, Industry dropdown, Major dropdown, Search input
- Modal for add/edit with form fields (keyword input, category select, industryType, major select, status toggle)
- Delete confirmation dialog
- Create button and actions (Edit, Delete)

#### `templates/admin/layout.html` (MODIFIED)
- Added sidebar navigation links:
  - **Career Objectives** → `/admin/career-objectives`
  - **Resume Keywords** → `/admin/resume-keywords`

---

## Phase 2: Student API Routes

### Files Modified

#### `routes/student.py` (MODIFIED)

**New Serializer Functions:**
```python
_serialize_resume_summary(doc)      # _id, title, createdAt, updatedAt, createdBy
_serialize_resume_full(doc)         # All fields: education, experience, projects, skills, etc.
_serialize_career_objective(doc)    # _id, text, major, approvalStatus, createdBy
_serialize_resume_keyword(doc)      # _id, keyword, category, industryType, major, isActive
```

**Career Objectives Endpoints:**
- `GET /api/student/career-objectives` 
  - Params: `major` (optional), `q` (optional search)
  - Returns: List of approved/active objectives filtered by major
  - Purpose: Populate dropdown in resume builder

- `POST /api/student/career-objectives/submit`
  - Body: `{ text, major (optional) }`
  - Returns: Created CareerObjective with approvalStatus: pending
  - Purpose: Students submit custom objectives for admin approval

**Resume Keywords Endpoints:**
- `GET /api/student/resume-keywords`
  - Params: `category` (REQUIRED: skill/technical/experience/project/volunteering), `major` (optional), `industryType` (optional), `q` (optional search)
  - Returns: List of keywords matching filters
  - Purpose: Load keyword library for each section in resume builder

**Resumes CRUD Endpoints:**
- `GET /api/student/resumes`
  - Pagination: limit, skip
  - Returns: List of user's resumes (summary serialization)

- `POST /api/student/resumes`
  - Body: `{ title }`
  - Returns: Created Resume with _id
  - Sets createdBy to current user, status: draft

- `GET /api/student/resumes/<id>`
  - Returns: Full Resume document (full serialization)
  - Ownership check: Verify resume belongs to user

- `PUT /api/student/resumes/<id>`
  - Body: Full resume payload (education, experience, skills, etc.)
  - Returns: Updated Resume
  - Auto-save handler for form updates
  - Ownership check

- `DELETE /api/student/resumes/<id>`
  - Returns: Success message
  - Ownership check

**PDF Generation Endpoint:**
- `GET /api/student/resumes/<id>/pdf`
  - Returns: PDF file (inline display in browser)
  - Flow: Render resume_pdf_template.html via render_template() → Pass resume doc + user profile → Call utils/pdf.generate_pdf_from_html()
  - Ownership check

#### `routes/pages.py` (MODIFIED)

**New Page Routes:**
- `GET /student/resume/builder` 
  - Renders: `templates/student/resume_builder.html`
  - Purpose: Create new resume (no resume_id in URL)

- `GET /student/resume/<resume_id>/builder`
  - Renders: `templates/student/resume_builder.html` with resume_id
  - Purpose: Edit existing resume (resume_id in URL query params)

---

## Phase 3: PDF Template

### Files Created

#### `templates/resume_pdf_template.html` (NEW)

**Purpose:** Jinja2 HTML template for professional resume PDF rendering

**Design:**
- Font: Google Fonts Inter (clean sans-serif)
- Colors: Black text (#0f172a), Navy headings (#0f172a), Light gray backgrounds (#f1f5f9)
- Layout: A4 format (margins handled by Playwright: 25.4mm all sides)
- Typography: Name 22px, Subheadings 13px, Body 11px

**Template Variables:**
- `resume` — Resume MongoEngine document
- `user` — User profile document

**Sections (11 total, rendered conditionally if data present):**

1. **Header**
   - Full name (22px, bold)
   - Email | Phone | Location (13px, muted)
   - Photo (optional, 60x60px thumbnail)

2. **Career Objective** *(if careerObjectiveEnhanced or careerObjectiveRaw)*
   - Section title: "Career Objective"
   - Content: Displays enhanced version if available, else raw

3. **Education** *(if education list not empty)*
   - Degree Name | College/University (13px bold | 11px normal)
   - Year | CGPA/Percentage (11px muted)

4. **Experience** *(if experience list not empty)*
   - Company | Position (13px bold)
   - Enhanced duties (if available) or raw keywords as bullet list
   - Year/duration info

5. **Skills** *(if skills list not empty)*
   - Comma-separated skill chips in 11px
   - Light blue background pills

6. **Technical Skills** *(if technicalSkills list not empty)*
   - Same format as Skills

7. **Projects** *(if projects list not empty)*
   - Project title (13px bold)
   - Keywords as bullet list or comma-separated

8. **Volunteering** *(if volunteering list not empty)*
   - Organization | Role (13px bold)
   - Duration | Keywords

9. **Certifications** *(if certifications list not empty)*
   - Certification Name | Authority (13px bold)
   - Year (11px muted)

10. **Languages** *(if languages list not empty)*
    - Language | Proficiency (11px)

11. **Footer** (optional)
    - Timestamp, page count

**CSS:**
- Professional typography with consistent spacing
- Section separators (light borders)
- Keyword pill styling (light blue background, 11px sans-serif)
- Print-optimized styles (@media print)
- A4 page break handling
- No header/footer in PDF (handled by Playwright)

---

## Phase 4: Student Frontend

### Files Created

#### `templates/student/resume_builder.html` (NEW)

**Purpose:** Complete student-facing resume builder UI with form management, auto-save, and PDF integration

**Layout:** 3-column responsive grid (matching create_report.html pattern)
```
[LEFT SIDEBAR] [CENTER FORM] [RIGHT SIDEBAR]
200px          flexible      240px
```

### Left Sidebar — Section Navigation
- **Component:** `.section-card` with sticky positioning (top: 84px)
- **Content:** 9 numbered sections with scroll-spy active highlighting
  1. Personal
  2. Career Obj.
  3. Education
  4. Experience
  5. Skills
  6. Projects
  7. Volunteer.* (optional)
  8. Certs.* (optional)
  9. Languages

- **Features:**
  - On-click scroll to section with smooth behavior
  - IntersectionObserver for active highlighting
  - Visual feedback: Highlight changes section-item background & dot color

### Center Column — Form Sections
**9 Resume Sections with Smart Form Management:**

1. **Personal Information**
   - Text inputs: fullName, email, phone, address
   - Pre-filled from `/api/student/profile`
   - On-input auto-save (500ms debounce)

2. **Career Objective**
   - Dropdown populated from `GET /api/student/career-objectives?major=X`
   - Shows approved objectives for user's major
   - "✏ Write my own" option for custom text
   - Falls back to textarea for custom input
   - Visual feedback: Selected objective shown in pill, Edit button to modify

3. **Education** (Dynamic entries)
   - Per-entry form: degreeName, college, year (select), CGPA/percentage
   - +Add button creates new card (incrementing index)
   - Remove button (✕) for entries > 0
   - Auto-save on input

4. **Experience** (Dynamic entries)
   - Per-entry form: company, position
   - Keyword library: `GET /resume-keywords?category=experience&major=X`
   - Selected keywords stored in `experienceKeywords.get(idx)` Map
   - Keyword chips with × remove buttons
   - Auto-save on keyword toggle

5. **Skills** (Keyword chips)
   - Search input for filtering skill library
   - Keyword library from `GET /resume-keywords?category=skill`
   - Selected keywords rendered as chips with × remove
   - Custom skill input: type + Enter to add custom skills
   - Auto-save on chip change

6. **Technical Skills** (Keyword chips)
   - Identical to Skills section but category: technical
   - Separate library and storage (techSkillsChips Set)

7. **Projects** (Dynamic entries)
   - Per-entry: project title
   - Keyword library for project points
   - Selected keywords as chips
   - Auto-save on change

8. **Volunteering** (Dynamic entries, optional)
   - Per-entry: organization, role, duration
   - Contribution keyword chips
   - Auto-save on change

9. **Certifications** (Dynamic entries, optional)
   - Per-entry: certification name, issuing authority, year (select)
   - Auto-save on change

10. **Languages** (Dynamic entries)
    - Per-entry: language name, proficiency (dropdown: Basic/Intermediate/Advanced/Fluent)
    - Auto-save on change

**Form Actions:**
- Submit button: "Generate Resume" → PUT `/api/student/resumes/<id>` → Download PDF
- Auto-save (500ms debounce): Triggered on any input/oninput event

### Right Sidebar — Profile Summary & PDF
- **Component:** `.summary-card` with sticky positioning (top: 84px)
- **Summary Rows:**
  - College (from profile)
  - Degree (from profile)
  - Major (from profile)

- **PDF Buttons:**
  - "View Preview" — Opens PDF in new tab (preview only)
  - "Download PDF" → Calls `/api/student/resumes/<id>/pdf`
  - Disabled until resume created (enabled after first save)

### JavaScript Features

**Data Structures:**
```javascript
let skillsChips = new Set()              // Selected skill keywords
let techSkillsChips = new Set()          // Selected technical skills
const experienceKeywords = new Map()     // entryIdx -> Set of keywords
const projectKeywords = new Map()        // entryIdx -> Set of keywords
const volunteeringKeywords = new Map()   // entryIdx -> Set of keywords
```

**Key Functions:**

1. **`autoSave()`**
   - 500ms debounce timer
   - Calls `buildResumePayload()`
   - PUT `/api/student/resumes/<id>` with JSON payload
   - Logs success/error to console

2. **`buildResumePayload()`**
   - Serializes entire form into Resume model format:
     ```javascript
     {
       fullName, email, phone, address, careerObjectiveRaw,
       education: [{degreeName, collegeUniversityName, passingYear, percentageCgpa, sortOrder}, ...],
       experience: [{companyName, position, rawDutyKeywords, sortOrder}, ...],
       skills: [...],
       technicalSkills: [...],
       projects: [{title, rawKeywords, sortOrder}, ...],
       volunteering: [{organizationName, role, duration, rawContributionKeywords, sortOrder}, ...],
       certifications: [{certificationName, issuingAuthority, year, sortOrder}, ...],
       languages: [{languageName, proficiency, sortOrder}, ...]
     }
     ```

3. **`loadCareerObjectives(majorId)`**
   - Fetches `GET /api/student/career-objectives?major=majorId`
   - Populates dropdown with preset objectives
   - Adds "✏ Write my own" option
   - Event handler: on change → show/hide textarea or display selected objective

4. **`loadResumeKeywords(category, containerId, selectedSet, entryIdx)`**
   - Fetches `GET /api/student/resume-keywords?category=X&major=Y&industryType=Z`
   - Renders keyword chips with click handlers
   - Highlights selected keywords (.selected class)
   - Re-renders on toggle

5. **`toggleResumeKeyword(keyword, category, entryIdx)`**
   - Global function for keyword chip clicks
   - Adds/removes keyword from appropriate Set (skillsChips, experienceKeywords.get(idx), etc.)
   - Re-renders chips and library display
   - Triggers auto-save

6. **Dynamic Entry Management**
   - `addEducationEntry()` — Create new education card with incrementing index
   - `removeEducationEntry(idx)` — Remove card and auto-save
   - Similar functions for: experience, projects, volunteering, certifications, languages
   - Each entry gets unique `data-*-idx` attribute for tracking

7. **Section Navigation**
   - Click handler on `.section-item` → scroll to section with smooth behavior
   - IntersectionObserver monitors section visibility → update active highlight in left nav

8. **Profile & Resume Bootstrap**
   - On page load: Fetch `/api/student/profile` → Pre-fill personal info fields
   - Check URL for `resume_id` query param:
     - If present: `GET /api/student/resumes/<id>` → Load all fields into form
     - If absent: `POST /api/student/resumes` → Create new resume, redirect with resume_id
   - Load keyword libraries for all sections
   - Enable PDF buttons once resume created

**Styling & UX:**
- **Responsive:** 3-column layout on desktop, stacked on tablet/mobile
- **Color scheme:** Blue (#1d4ed8, #2563eb, #3b82f6) accents, light gray (#f8fbff) backgrounds
- **Animations:** Smooth section scrolling, keyword chip transitions, button hovers
- **Accessibility:** Form labels, semantic HTML, color contrast

### CSS Architecture
- **Layout:** CSS Grid 3-column with gap: 16px
- **Cards:** Border 1px #dbe7ff, shadow, border-radius: 16px
- **Buttons:** Gradient blue backgrounds with hover effects
- **Inputs:** Light blue background (#f8fbff), dark border on focus (#60a5fa)
- **Chips:** Pill-shaped badges with toggle styling
- **Sticky:** Left/right sidebars stick to top: 84px (navbar height)
- **Print styles:** Optimized for PDF export via Playwright

---

## Summary of Code Changes

### New Files (5)
1. `models/resume.py` — Core Resume data model with embedded documents
2. `models/career_objective.py` — Career objective approval workflow
3. `models/resume_keyword.py` — Resume keyword library
4. `templates/admin/manage_career_objectives.html` — Admin CRUD UI
5. `templates/admin/manage_resume_keywords.html` — Admin CRUD UI
6. `templates/resume_pdf_template.html` — Professional resume PDF template
7. `templates/student/resume_builder.html` — Complete student resume builder form

### Modified Files (4)
1. `models/__init__.py` — Added Resume*, CareerObjective, ResumeKeyword exports
2. `routes/admin.py` — Added 8 admin endpoints + 2 serializers
3. `routes/student.py` — Added 11 student endpoints + 4 serializers
4. `routes/pages.py` — Added 2 new page routes
5. `templates/admin/layout.html` — Added sidebar links to admin pages

### API Endpoints Created (19 Total)

**Admin APIs (8):**
- GET/POST/PUT/DELETE Career Objectives
- GET/POST/PUT/DELETE Resume Keywords

**Student APIs (11):**
- GET Career Objectives
- POST Career Objectives Submit
- GET Resume Keywords
- GET/POST/PUT/DELETE Resumes
- GET Resume PDF

**Page Routes (2):**
- GET /student/resume/builder
- GET /student/resume/<id>/builder

---

## Testing Checklist

- ✅ Import validation: `py -3 -c "import app"` (Phase 1, 2, 3 all pass)
- ✅ All blueprints registered successfully
- ✅ Admin pages load without errors
- ✅ Student resume builder page loads with 3-column layout
- ⏳ Functional testing: Create resume → Auto-save → Generate PDF
- ⏳ Career objective dropdown workflow
- ⏳ Keyword chip management and selection
- ⏳ Profile pre-fill from `/api/student/profile`
- ⏳ PDF rendering and download

---

## Future Enhancements (Phase 5+)

- **AI Enhancement Workflow:** POST `/api/student/resumes/<id>/generate` → Call n8n workflow for enhanced content
- **Live Preview:** Real-time PDF preview before download
- **AI Polish:** Automated copyediting for resume sections
- **Template Variants:** Multiple resume template designs
- **Export Formats:** DOCX, TXT in addition to PDF

# QUICK API REFERENCE - Hierarchical Report Sections

## Pagination (List Endpoints)

Most list-style endpoints in admin/student APIs now support optional query params:

```bash
?limit=<n>&offset=<n>
```

- `limit` is optional and clamped to safe endpoint-specific maximums.
- `offset` is optional, defaults to `0`, and negative/invalid values are treated as `0`.
- If no pagination params are provided, previous default behavior is preserved (backward compatible).

Examples:

```bash
GET /api/student/universities?limit=25&offset=0
GET /api/student/colleges?university=<id>&limit=25&offset=25
GET /api/admin/users?role=student&limit=100&offset=200
GET /api/admin/reports?limit=50&offset=0
```

Notes:

- Endpoint response shape is unchanged (still returns a JSON array for these list APIs).
- Existing UI pages continue working without changes because default limits/caps remain in effect when pagination params are omitted.

## Authentication
All endpoints require admin token in header:
```
Authorization: Bearer <admin_token>
```

---

## 1️⃣ UNIVERSITY REPORT TEMPLATES

### Get University Template (Auto-creates if not found)
```bash
GET /api/admin/university-report-templates/<university_id>

Response:
{
  "_id": "507...",
  "university": { "_id": "...", "name": "Ahmedabad University" },
  "sections": [
    { "key": "introduction", "title": "Introduction", "description": "...", "sortOrder": "0" },
    { "key": "objectives", "title": "Objectives", "description": "...", "sortOrder": "1" },
    ...
  ],
  "description": "Default report structure for Ahmedabad University",
  "isActive": true,
  "createdBy": { "_id": "...", "name": "Admin Name" },
  "createdAt": "2026-04-23T10:00:00",
  "updatedAt": "2026-04-23T10:00:00"
}
```

### Update University Template
```bash
PUT /api/admin/university-report-templates/<university_id>
Content-Type: application/json

Body:
{
  "sections": [
    {
      "key": "introduction",
      "title": "Introduction",
      "description": "Project background and context",
      "sortOrder": "0"
    },
    {
      "key": "objectives",
      "title": "Objectives", 
      "description": "Project goals and targets",
      "sortOrder": "1"
    }
  ],
  "description": "Updated template for 2026",
  "isActive": true
}

Response: Updated template object
```

---

## 2️⃣ COLLEGE REPORT TEMPLATES

### Get College Template (Auto-creates inheriting from university)
```bash
GET /api/admin/college-report-templates/<college_id>

Response:
{
  "_id": "...",
  "college": { "_id": "...", "name": "DAIICT" },
  "university": { "_id": "...", "name": "Ahmedabad University" },
  "sections": [],
  "useUniversityDefault": true,  ← Toggle this to customize
  "description": "Inherits from Ahmedabad University template",
  "inheritedSections": [
    { "key": "introduction", "title": "Introduction", ... },
    { "key": "objectives", "title": "Objectives", ... }
  ],
  "isActive": true,
  "createdAt": "2026-04-23T10:00:00"
}
```

### Switch College to Custom (Override University)
```bash
PUT /api/admin/college-report-templates/<college_id>
Content-Type: application/json

Body:
{
  "useUniversityDefault": false,
  "sections": [
    {
      "key": "introduction",
      "title": "College-Specific Introduction",
      "description": "DAIICT project introduction format",
      "sortOrder": "0"
    },
    {
      "key": "technical_analysis",
      "title": "Technical Analysis",
      "description": "Deep technical analysis required",
      "sortOrder": "1"
    }
  ],
  "description": "DAIICT customized report structure"
}

Response: Updated template with useUniversityDefault=false
```

### Revert College to University Default
```bash
PUT /api/admin/college-report-templates/<college_id>

Body:
{
  "useUniversityDefault": true
}

Response: Template now using university's sections
```

---

## 3️⃣ MAJOR REPORT TEMPLATES

### Get Major Template (Auto-creates inheriting from college/university)
```bash
GET /api/admin/major-report-templates/<major_id>

Response:
{
  "_id": "...",
  "major": { "_id": "...", "name": "Computer Science" },
  "college": { "_id": "...", "name": "DAIICT" },
  "university": { "_id": "...", "name": "Ahmedabad University" },
  "sections": [],
  "useLevelAboveDefault": true,  ← Toggle to customize
  "inheritedSections": [
    { "key": "introduction", "title": "College-Specific Introduction", ... }
  ],
  "inheritanceLevel": "college",  ← Shows where it's coming from
  "description": "Inherits from college/university template",
  "isActive": true
}
```

### Customize Major (Override College/University)
```bash
PUT /api/admin/major-report-templates/<major_id>

Body:
{
  "useLevelAboveDefault": false,
  "sections": [
    {
      "key": "introduction",
      "title": "CSE Project Introduction",
      "description": "CSE major specific introduction",
      "sortOrder": "0"
    },
    {
      "key": "algorithm_analysis",
      "title": "Algorithm & Complexity Analysis",
      "description": "Required for CS projects",
      "sortOrder": "1"
    },
    {
      "key": "code_documentation",
      "title": "Code Documentation",
      "description": "Well-commented code with design patterns",
      "sortOrder": "2"
    }
  ],
  "description": "CSE customized sections"
}

Response: Updated with useLevelAboveDefault=false
```

### Revert Major to Inherited Sections
```bash
PUT /api/admin/major-report-templates/<major_id>

Body:
{
  "useLevelAboveDefault": true
}

Response: Major now uses college/university sections
```

---

## 🔍 UTILITY: Resolve Cascade Chain

### Get What Sections a Major Will Actually Use
```bash
GET /api/admin/majors/<major_id>/effective-report-sections

Response (if Major has custom sections):
{
  "sections": [
    { "key": "algorithm_analysis", "title": "Algorithm & Complexity Analysis", ... }
  ],
  "source": "major_custom",
  "majorId": "<major_id>"
}

Response (if College has custom sections):
{
  "sections": [
    { "key": "technical_analysis", "title": "Technical Analysis", ... }
  ],
  "source": "college_custom",
  "collegeId": "<college_id>"
}

Response (if Using University default):
{
  "sections": [
    { "key": "introduction", "title": "Introduction", ... }
  ],
  "source": "university_default",
  "universityId": "<university_id>"
}

Response (if nothing configured):
{
  "sections": [],
  "source": "none",
  "message": "No report sections configured at any level"
}
```

---

## 🧪 Example Workflow

### Setup Phase (One Time)
```bash
# 1. Configure University defaults
PUT /api/admin/university-report-templates/uni_123
{
  "sections": [
    { "key": "intro", "title": "Introduction", ... },
    { "key": "objectives", "title": "Objectives", ... },
    { "key": "methodology", "title": "Methodology", ... },
    { "key": "results", "title": "Results", ... },
    { "key": "conclusion", "title": "Conclusion", ... }
  ]
}

# 2. All colleges inherit (no action needed, auto-default to useUniversityDefault=true)
# 3. All majors inherit (no action needed, auto-default to useLevelAboveDefault=true)
```

### Override College Phase
```bash
# 1. Engineering college needs custom sections
PUT /api/admin/college-report-templates/college_eng
{
  "useUniversityDefault": false,
  "sections": [
    { "key": "intro", "title": "Introduction", ... },
    { "key": "technical_analysis", "title": "Technical Analysis", ... },
    { "key": "implementation", "title": "Implementation", ... }
  ]
}

# 2. Verify cascade
GET /api/admin/major-report-templates/major_cse
# Returns: source="college_custom", sections from Engineering college
```

### Fine-Tune Major Phase
```bash
# 1. CSE major needs further customization
PUT /api/admin/major-report-templates/major_cse
{
  "useLevelAboveDefault": false,
  "sections": [
    { "key": "intro", "title": "Introduction", ... },
    { "key": "algorithm_analysis", "title": "Algorithm Analysis", ... },
    { "key": "performance", "title": "Performance Metrics", ... }
  ]
}

# 2. Verify final cascade
GET /api/admin/majors/major_cse/effective-report-sections
# Returns: source="major_custom", CSE's specific sections
```

---

## 📝 Section Object Structure

```json
{
  "key": "unique_identifier_snake_case",
  "title": "Display Title",
  "description": "What this section should contain",
  "sortOrder": "0"
}
```

**Rules:**
- `key`: Required, must be unique per template, lowercase with underscores
- `title`: Required, user-visible section name
- `description`: Optional, guidance text for users
- `sortOrder`: Optional (defaults to array index), controls display order

---

## ⚡ Tips & Tricks

### Bulk Update All Majors Under a College
```bash
# 1. Update college template
PUT /api/admin/college-report-templates/<college_id>
{ "sections": [...], "useUniversityDefault": false }

# 2. All majors with useLevelAboveDefault=true now use new college sections
# 3. Majors with useLevelAboveDefault=false are unaffected (keep their custom)
```

### Check Inheritance Before Customizing
```bash
# 1. GET to see current state
GET /api/admin/major-report-templates/<major_id>
# Check: inheritedSections, inheritanceLevel

# 2. Decide: keep inherited OR customize
# 3. PUT with appropriate sections
```

### Revert Customization Easily
```bash
# Any level can revert to parent's sections in one call:
PUT /api/admin/<type>-report-templates/<id>
{ "use<ParentLevel>Default": true }

# College reverts to University:
PUT /api/admin/college-report-templates/<id>
{ "useUniversityDefault": true }

# Major reverts to College/University:
PUT /api/admin/major-report-templates/<id>
{ "useLevelAboveDefault": true }
```

---

## 🐛 Common Scenarios

### "I want all majors to have same sections"
```
1. Configure University template with desired sections
2. Ensure all Colleges have useUniversityDefault=true
3. Ensure all Majors have useLevelAboveDefault=true
4. Done! Change university template once → all majors updated
```

### "Engineering college needs different sections than Arts"
```
1. Engineering college: useUniversityDefault=false + custom sections
2. Arts college: useUniversityDefault=true (keep university's)
3. Majors automatically inherit from their college
```

### "CSE major needs special sections but IT doesn't"
```
1. Both under Engineering college with custom sections
2. CSE major: useLevelAboveDefault=false + custom sections
3. IT major: useLevelAboveDefault=true (uses college's sections)
```

---

## 📞 Status Codes

- `200`: Success (GET/PUT)
- `201`: Created (new template)
- `400`: Bad request (invalid sections format)
- `404`: Not found (invalid university/college/major ID)
- `403`: Forbidden (non-admin user)

---

Last Updated: 2026-04-23
System: ReportGen Hierarchical Report Sections

# Feature: Student Language Selector for Report Generation

## Goal
Add a **language selection dropdown** on the student "Create Report" page (`/student/create`) so students can **optionally override** the default report generation language. If the student does not select a language (leaves it as default), the system uses the admin-configured language from the Major's `reportLanguage` field (current behavior). If the student selects a specific language, the report generates in that language instead.

---

## Current Behavior (Understand Before Changing)

### How Language Works Today
1. **Admin configures** `Major.reportLanguage` (e.g., "English", "Gujarati", "Hindi") via the admin panel at **Manage Majors → Policies**
2. **Admin also configures** `Major.reportPolicy.allowedLanguages` (a list like `["English", "Hindi", "Gujarati"]`) and `Major.reportPolicy.strictLanguageOnly` (boolean)
3. When student creates a report, the **language is auto-set** from `major_doc.reportLanguage` — student has **NO choice**
4. On the Create Report page, `#majorInfo` shows read-only text: `"Language: English | Content: Text"` — purely informational
5. The language is stored on the Report document as `report.reportLanguage`
6. The language is sent to the n8n AI webhook as `reportConfig.language`

### Key Files & Line Numbers

#### Model: `models/report.py` (line 38)
```python
reportLanguage = StringField(default='English')
```
This stores the final language used for generation on the Report document.

#### Model: `models/major.py` (lines 20-21, 41)
```python
# Inside ReportPolicy (embedded document):
strictLanguageOnly = BooleanField(default=False)   # line 20
allowedLanguages = ListField(StringField(), default=list)  # line 21

# On Major itself:
reportLanguage = StringField(default='English')  # line 41
```

#### Report Creation API: `routes/reports.py` (line 798)
```python
report = Report(
    ...
    reportLanguage=major_doc.reportLanguage,  # ← HARDCODED from major
    ...
)
```
This is where `reportLanguage` is set on the Report — currently always from Major.

#### n8n Webhook Payload: `routes/reports.py` (line 950)
```python
'reportConfig': {
    'language': major_doc.reportLanguage,  # ← sent to AI
    ...
}
```
This tells the AI what language to write the report in.

#### Frontend `#majorInfo` Display: `templates/student/create_report.html` (line 1202-1203)
```javascript
document.getElementById('majorInfo').textContent =
    `Language: ${major.reportLanguage || 'English'} | Content: ${major.reportContentType || 'Text'}`;
```

#### Student Major API: `routes/student.py` (line 124-138)
```python
def _serialize_major(major):
    return {
        '_id': str(major.id),
        'name': major.name,
        ...
        'reportLanguage': major.reportLanguage,
        'reportContentType': major.reportContentType,
        'reportPolicy': major.reportPolicy.to_mongo().to_dict() if major.reportPolicy else {},
        ...
    }
```
This already returns `reportPolicy` (which includes `allowedLanguages` and `strictLanguageOnly`) and `reportLanguage` to the frontend.

#### Form Submission Payload: `templates/student/create_report.html` (lines 1392-1417)
```javascript
const payload = {
    degree: document.getElementById('degreeSelect').value,
    major: document.getElementById('majorSelect').value,
    projectTitle: document.getElementById('projectTitle').value.trim(),
    // ... other fields
    // NOTE: NO language field is sent currently!
};
```

---

## Changes Required

### 1. Frontend: `templates/student/create_report.html`

#### A. Add Language Dropdown HTML (inside `#step1-section`, after the Major `col-md-4` div, around line 614-618)

Add a new row inside the Step 1 section for the language selector. Place it **after** the Major dropdown and **before** the `step1Hint` small text.

```html
<!-- Add after line 614 (after majorInfo div, before the col-12 hint) -->
<div class="col-md-6" id="languageSelectorWrap" style="display: none;">
    <label class="form-label">Report Language</label>
    <select class="form-select" id="reportLanguageSelect">
        <option value="">Default (set by admin)</option>
    </select>
    <small class="text-muted" style="font-size:11px;" id="languageHint">
        Leave as default to use the language configured by admin.
    </small>
</div>
```

**Design requirements:**
- The dropdown should be **hidden by default** (`display: none`)
- It should **appear only after a major is selected** (similar to how `#majorInfo` badge works)
- The first option should always be `""` (empty value) with label "Default (set by admin)" — this means "use major's default language"
- Other options should be populated from `major.reportPolicy.allowedLanguages` array
- If `allowedLanguages` is empty or only has 1 language, **hide the dropdown** entirely (no choice needed)
- If `major.reportPolicy.strictLanguageOnly` is `true`, **hide the dropdown** (admin locked the language)
- Style should match the existing form-select styling already in the page

#### B. Update `renderMajorInfo()` function (around line 1192-1204)

After fetching major details, **also populate the language dropdown**:

```javascript
const renderMajorInfo = async (majorId) => {
    const languageWrap = document.getElementById('languageSelectorWrap');
    const languageSelect = document.getElementById('reportLanguageSelect');

    if (!majorId) {
        document.getElementById('majorInfo').textContent = '';
        languageWrap.style.display = 'none';
        return;
    }

    const res = await fetch(`/api/student/major/${majorId}`, {
        credentials: 'include',
        headers: authHeaders()
    });
    const major = await res.json();

    document.getElementById('majorInfo').textContent =
        `Language: ${major.reportLanguage || 'English'} | Content: ${major.reportContentType || 'Text'}`;

    // Populate language selector
    const allowedLanguages = major.reportPolicy?.allowedLanguages || [];
    const strictLanguage = major.reportPolicy?.strictLanguageOnly || false;
    const defaultLanguage = major.reportLanguage || 'English';

    // Show dropdown only if: not strict AND there are 2+ allowed languages
    if (!strictLanguage && allowedLanguages.length >= 2) {
        languageSelect.innerHTML =
            `<option value="">Default (${defaultLanguage})</option>` +
            allowedLanguages
                .map(lang => `<option value="${lang}">${lang}</option>`)
                .join('');
        languageWrap.style.display = '';

        // Update the hint text
        document.getElementById('languageHint').textContent =
            `Default is "${defaultLanguage}". You can choose a different language for your report.`;
    } else {
        languageWrap.style.display = 'none';
        languageSelect.innerHTML = '<option value="">Default</option>';
    }
};
```

#### C. Include language in the form submission payload (around line 1392-1417)

Add the selected language to the payload object:

```javascript
const payload = {
    degree: document.getElementById('degreeSelect').value,
    academicDepartment: document.getElementById('departmentSelect').value,
    major: document.getElementById('majorSelect').value,
    projectTitle: document.getElementById('projectTitle').value.trim(),
    // ... existing fields ...
    reportLanguage: document.getElementById('reportLanguageSelect').value || '',  // ← ADD THIS
    // ... rest of existing fields ...
};
```

#### D. Reset language dropdown when major changes

In the `handleMajorChange` function (around line 1281-1298) and `handleDegreeChange` / `handleDepartmentChange`, ensure the language dropdown resets:

The `renderMajorInfo(majorId)` call already handles this since we modified it above. But also add a reset in `resetProjectTitle()` or create a separate reset:

```javascript
// Inside handleDegreeChange and handleDepartmentChange, the renderMajorInfo('') 
// call via loadMajors will automatically hide and reset the language dropdown.
// No additional code needed if renderMajorInfo handles the empty majorId case.
```

---

### 2. Backend: `routes/reports.py`

#### A. Report Creation — Accept `reportLanguage` from frontend (around line 789-798)

Modify the report creation logic to check for a student-provided language override:

```python
# Around line 781 (after major_doc lookup)
major_doc = Major.objects(id=major_id).first()
if not major_doc:
    return jsonify({'message': 'Major not found'}), 404

# Determine report language: student override OR major default
student_language = str(data.get('reportLanguage') or '').strip()
if student_language:
    # Validate against allowed languages (if policy exists)
    policy = major_doc.reportPolicy
    allowed = list(policy.allowedLanguages) if policy and policy.allowedLanguages else []
    strict = bool(policy.strictLanguageOnly) if policy else False

    if strict:
        # Admin locked the language — ignore student override
        effective_language = major_doc.reportLanguage
    elif allowed and student_language not in allowed:
        # Student picked a language not in the allowed list — reject
        return jsonify({'message': f'Language "{student_language}" is not allowed for this major. Allowed: {", ".join(allowed)}'}), 400
    else:
        effective_language = student_language
else:
    effective_language = major_doc.reportLanguage

# Then use effective_language instead of major_doc.reportLanguage:
report = Report(
    ...
    reportLanguage=effective_language,  # ← CHANGED from major_doc.reportLanguage
    ...
)
```

#### B. n8n Webhook Payload — Use report's language instead of major's (around line 950)

Change the webhook payload to use the report's stored language (which may be the student override):

```python
'reportConfig': {
    'language': report.reportLanguage,  # ← CHANGED from major_doc.reportLanguage
    'contentType': major_doc.reportContentType,
    ...
}
```

This ensures the AI generates in the student's selected language.

---

### 3. Backend: `routes/admin.py` (line 1479 and 1557)

The admin report regeneration flow also hardcodes `major_doc.reportLanguage`. Update these to use the existing `report.reportLanguage` stored on the report:

#### Line 1479 (admin report regeneration):
```python
# Change from:
reportLanguage=major_doc.reportLanguage,
# Change to:
reportLanguage=report.reportLanguage,  # Preserve student's language choice on regeneration
```

#### Line 1557 (admin n8n payload):
```python
# Change from:
'language': major_doc.reportLanguage,
# Change to:
'language': report.reportLanguage,  # Use the report's stored language (may be student override)
```

---

### 4. NO Model Changes Needed

- `Report.reportLanguage` already exists as `StringField(default='English')` — this field will now store either the major default OR the student's override
- `Major.reportPolicy.allowedLanguages` already exists as `ListField(StringField())` — this provides the dropdown options  
- `Major.reportPolicy.strictLanguageOnly` already exists as `BooleanField` — this controls whether override is allowed
- `Major.reportLanguage` still serves as the default — no changes needed

---

## Complete Data Flow After Changes

```
Student Opens Create Report Page
    → Selects Major
    → Frontend calls GET /api/student/major/{id}
    → Response includes: reportLanguage, reportPolicy.allowedLanguages, reportPolicy.strictLanguageOnly
    
    IF strictLanguageOnly == true OR allowedLanguages.length < 2:
        → Language dropdown stays HIDDEN
        → Default language from major is used
    ELSE:
        → Language dropdown APPEARS with options from allowedLanguages
        → First option: "Default ({majorLanguage})" with value=""
        
Student Submits Form
    → Payload includes: reportLanguage: "" (default) or "Hindi" (override)
    
Backend Processes
    → IF reportLanguage is empty → use major_doc.reportLanguage
    → IF reportLanguage is provided:
        → IF strictLanguageOnly → ignore override, use major default
        → IF not in allowedLanguages → return 400 error
        → ELSE → use student's choice
    → Store final language in report.reportLanguage
    → Send to n8n webhook as reportConfig.language
```

---

## Summary of Files to Modify

| File | What to Change |
|------|---------------|
| `templates/student/create_report.html` | Add language `<select>` HTML in Step 1, update `renderMajorInfo()` to populate it, add `reportLanguage` to submission payload |
| `routes/reports.py` | Accept `reportLanguage` from payload at report creation (line ~798), validate against policy, use `report.reportLanguage` in webhook (line ~950) |
| `routes/admin.py` | Use `report.reportLanguage` instead of `major_doc.reportLanguage` in admin regeneration (lines ~1479, ~1557) |

**No model changes needed.** All required fields already exist.

# HIERARCHICAL REPORT SECTIONS MANAGEMENT SYSTEM

## Architecture Overview

This implementation follows proven SaaS patterns (Salesforce, Slack, WordPress) with a **3-level Settings Cascade with Visual Inheritance**:

```
UNIVERSITY LEVEL (Base Template)
├── Default sections for entire university
├── Applied to all colleges unless overridden
└── Example: Introduction, Objectives, Methodology, Results, Conclusion

    ↓

COLLEGE LEVEL (Optional Override)
├── Custom sections for specific college
├── Inherits from University if "useUniversityDefault=true"
├── Overrides University for all majors in college unless overridden
└── Example: College-specific evaluation criteria

    ↓

MAJOR LEVEL (Final Customization)
├── Specific customization for individual major
├── Inherits from College (or University) if "useLevelAboveDefault=true"
├── Highest priority - final configuration used in reports
└── Example: CSE-specific project structure, BCA-specific format
```

## Data Models Created

### 1. ReportSectionItem (Embedded Document)
- Used within University/College/Major templates
- Fields: key, title, description, sortOrder

### 2. UniversityReportTemplate
- One per University (unique constraint)
- Contains default sections for entire university
- Auto-created with 5 default sections on first access

### 3. CollegeReportTemplate
- One per College (unique constraint)
- `useUniversityDefault` flag: toggle between inheritance and customization
- If True: sections field is ignored, uses University sections
- If False: uses custom sections stored in this document

### 4. MajorReportTemplate
- One per Major (unique constraint)
- `useLevelAboveDefault` flag: toggle between inheritance and customization
- If True: sections field is ignored, cascades to College/University
- If False: uses custom sections stored in this document

## API Endpoints Added

### University Level
```
GET  /api/admin/university-report-templates/<university_id>
PUT  /api/admin/university-report-templates/<university_id>
```

### College Level
```
GET  /api/admin/college-report-templates/<college_id>
PUT  /api/admin/college-report-templates/<college_id>
```

### Major Level
```
GET  /api/admin/major-report-templates/<major_id>
PUT  /api/admin/major-report-templates/<major_id>
```

### Utility
```
GET  /api/admin/majors/<major_id>/effective-report-sections
     → Returns resolved sections following cascade logic
     → Shows which level (university/college/major) is providing the sections
```

## Key Features

1. **Auto-Creation**: Templates are auto-created on first access with sensible defaults
2. **Inheritance Chain**: GET endpoints return `inheritedSections` showing what sections would be inherited
3. **Toggle-Based Customization**: Single boolean flag (`useUniversityDefault` / `useLevelAboveDefault`) to switch between inheritance and customization
4. **Cascade Resolution**: `effective-report-sections` endpoint resolves the entire cascade chain to show what the major will actually use
5. **Visual Indicators**: Response includes `inheritanceLevel` to show where sections are coming from
6. **Audit Trail**: All changes tracked with `createdBy` and timestamps

## Benefits vs Original Approach

### BEFORE (Embedded in Major)
- Every major had to manually configure all sections
- 100+ majors = 100+ section configurations (labor-intensive)
- Difficult to maintain university-wide standards
- No way to bulk-apply changes

### AFTER (Hierarchical)
- Set once at University level → applies to all colleges/majors
- Override at College level for specific colleges
- Fine-tune at Major level for exceptional cases
- Single change at University level updates all majors
- Exactly like Skillinc's grading system (as client requested)

## Example Workflows

### Workflow 1: Uniform Structure (Most Common)
```
1. Admin sets 5 standard sections at University level
2. All colleges inherit (useUniversityDefault=true)
3. All majors inherit (useLevelAboveDefault=true)
4. Result: Consistent report structure across university
5. Change: Edit University template once → all majors updated
```

### Workflow 2: College-Specific Customization
```
1. University has default 5 sections
2. Engineering College sets useUniversityDefault=false, adds 8 custom sections
3. Arts College uses useUniversityDefault=true (inherits University)
4. All majors in Engineering inherit College's 8 sections
5. All majors in Arts inherit University's 5 sections
```

### Workflow 3: Major-Specific Customization
```
1. University has default 5 sections
2. College overrides with 8 sections
3. CSE Major sets useLevelAboveDefault=false, adds 12 custom sections
4. Other majors in college inherit the 8 sections
5. CSE Major uses its specific 12 sections
```

## Tested Scenarios

✅ Auto-creation of templates on first access
✅ Toggle inheritance on/off per level
✅ Cascade resolution following correct priority
✅ Section validation (key and title required)
✅ Timestamp and audit tracking
✅ Backward compatibility (old majors unaffected)

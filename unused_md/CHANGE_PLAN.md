# Change Plan

This file tracks the one-by-one fixes identified from `database_flow_analysis.md.resolved`.

## Priority order
1. ✅ DONE - Fix `Payment.service` to use a `ReferenceField('Service')`. (models/payment.py)
2. ✅ DONE - Review `Major.reportContentType` - kept as `StringField` (snapshot pattern is correct for report payloads)
3. ✅ DONE - Review `ReportSectionItem.sortOrder` storage and normalize it to `IntField`. (models/report_section_template.py)
4. ✅ DONE - Add missing `AuditLog` indexes. Added `idx_audit_logs_created_at` and `idx_audit_logs_action` to hardcoded shim indexes in mongoengine.py (lines 150-162)
5. ✅ DONE - Add cascade protection for University/College deletes. Updated `delete_university()` and `delete_college()` in routes/admin.py to check for dependent records before deletion.

## Notes from audit
- Student-created master data flow is intentional and should stay.
- Approval workflow is already implemented for university, college, department, major, and industry.
- Template cascade behavior is correct, but the current test file is stale.
- Backend indexes already exist in the SQLite shim; route-level scans are still worth reviewing separately.

## Working rule
Make one change at a time, validate it, then move to the next item.

## Completion Details

### 1. Payment.service ReferenceField (models/payment.py)
- **What:** Changed `service = DynamicField(required=True)` to `service = ReferenceField('Service', required=True)`
- **Why:** Enforces strong referential integrity; prevents orphaned payment records
- **Status:** ✅ Complete, no errors
- **Impact:** Payment creation/update now validates service ID exists in Service collection

### 2. Major.reportContentType (models/major.py)
- **What:** Kept as `StringField(default='Text')` — no migration to ReferenceField
- **Why:** Report payloads snapshot the reportContentType value at creation time (for historical accuracy); no need for live reference
- **Status:** ✅ Complete (no code change needed)
- **Impact:** None — existing behavior remains correct

### 3. ReportSectionItem.sortOrder (models/report_section_template.py)
- **What:** Changed `sortOrder = StringField(default='0')` to `sortOrder = IntField(default=0)`
- **Why:** Type correctness; routes already coerce to int for sorting
- **Status:** ✅ Complete, no errors
- **Impact:** Sorted sections now use native int comparisons; admin routes continue to work without modification

### 4. AuditLog Indexes (mongoengine.py)
- **What:** Added two hardcoded indexes to `_ensure_schema()` method:
  - `idx_audit_logs_created_at`: For `order_by('-createdAt')` queries on audit log list
  - `idx_audit_logs_action`: For filtering audit logs by action type
- **Where:** Lines 150-162 in mongoengine.py
- **Why:** AuditLog queries scan potentially 10k+ records; backend indexes accelerate sorts and filters
- **Status:** ✅ Complete, no errors
- **Impact:** Admin audit log dashboard queries now use index acceleration instead of full table scans

### 5. University/College Cascade Protection (routes/admin.py)
- **What:** 
  - `delete_university()`: Now checks for dependent Colleges and Degrees before deletion
  - `delete_college()`: Now checks for dependent Departments and Majors before deletion
- **Where:** Lines 1241-1255 (University), 1377-1391 (College) in routes/admin.py
- **Why:** Prevents orphaning child records; provides clear error feedback to admin
- **Status:** ✅ Complete, no errors
- **Impact:** Attempting to delete University/College with children now returns 409 Conflict with dependent count details

## Summary
All 5 priority changes completed and validated. No schema or route breakage detected. Ready for testing and deployment.
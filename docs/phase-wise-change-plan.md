# Phase-wise Prompt: Admin UI & Backend Changes

Purpose: a concise, phased prompt template to guide iterative changes to the admin UI and backend (dependent dropdowns, serializers, pagination, and related fixes). Use each phase as a separate request to the assistant so changes can be applied, tested, and rolled back safely.

---

**How to use:**
- For each phase, copy the "Assistant Prompt" section and paste it as a single request to the coding agent.
- Include results of the previous phase (test output, `git diff`, or server logs) when moving to the next phase.
- Run the short validation steps after applying patches.

---

## Phase 1 — Discover & Triage
Goal: Map all affected code paths and reproduce the issue locally.

Files to inspect:
- `routes/admin.py`
- All `templates/admin/*.html` (especially `manage_majors.html`, `manage_project_titles.html`)
- `models/*` for optional fields accessed directly (e.g., `industry.logo`)
- `mongoengine.py` (custom adapter behavior)

Assistant Prompt (Phase 1):
- "Scan the repository for admin routes and templates that handle degrees, majors, departments, and project titles. Produce a short list of files and the functions that read/write dependent dropdowns and serializers that access optional fields directly. Include any API endpoints used by the admin pages (e.g., `/api/admin/departments`, `/api/admin/degrees`, `/api/admin/majors`) and note whether endpoints return arrays or `{items,total}`. Also produce suggested quick reproduction steps to see the empty dropdown in the browser."

Commands to run locally (developer):
- Start the server: `python app.py` or `flask run` (as applicable)
- Reproduce in browser: open `http://127.0.0.1:5000/admin/majors` and click "Add Major"
- Curl check endpoint: `curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/admin/departments?degree=<degreeId>"`

Validation checklist (Phase 1):
- Confirm which templates call which API endpoints.
- Confirm if endpoints return arrays or paged objects.
- Confirm whether server-side serializers access optional attributes directly and may raise AttributeError.

---

## Phase 2 — Small Safe Fixes (Frontend first)
Goal: Make minimal frontend edits to ensure modal open always refreshes dependent dropdowns and keeps selects enabled.

Assistant Prompt (Phase 2):
- "Apply minimal, localized frontend fixes: on `manage_majors.html` and `manage_project_titles.html` ensure the Add modal's `open*Modal()` functions set an internal selected-degree state, call a `refreshDependentOptions()` helper, and keep the dependent `<select>` enabled. Fix any `id` mismatches in `setDepartmentOptions`/`setMajorOptions` and add a short console.log for debug. Return an `apply_patch` diff that only edits the template files."

Files to change (example):
- `templates/admin/manage_majors.html`
- `templates/admin/manage_project_titles.html`

Small tests to run after patch:
- Hard-refresh browser (Ctrl+F5), open Admin -> Majors, click Add Major, pick Degree -> Department list populates.
- Inspect console for the debug log added.

Rollback: revert commit or `git checkout -- templates/admin/manage_majors.html` if issues.

Acceptance: dropdown populates reliably on modal open and degree change.

---

## Phase 3 — Backend Robustness
Goal: Patch server-side serializers and API responses to avoid 500s and to be consistent about response shapes.

Assistant Prompt (Phase 3):
- "Scan `routes/admin.py` and serializers used by admin endpoints; replace direct property accesses like `doc.logo` with safe access `getattr(doc, 'logo', '')` or `doc._data.get('logo')` fallback to avoid AttributeError with the custom ORM. Make API endpoints return `{ items, total }` for paginated endpoints or document which endpoints return arrays. Provide an `apply_patch` diff and tests to run."

Files to change:
- `routes/admin.py` (serializers and endpoints for departments, universities, payments, industries)

Tests:
- Call endpoints used by admin pages and ensure HTTP 200 + JSON parseable.
- Example: `curl -i "http://127.0.0.1:5000/api/admin/industries"`

Acceptance: No server 500 when admin pages load; pages receive JSON and render rows.

---

## Phase 4 — Pagination & Performance
Goal: Replace client-side full-list pagination with server-side paged responses for large admin lists, or keep a short-term client-side cap with clear limits.

Assistant Prompt (Phase 4):
- "For the largest admin lists (`payments`, `users`, `reports`, `work-keywords`), implement server-side pagination: accept `limit` and `offset` query params and return `{ items, total, limit, offset }`. Update the corresponding templates to send `limit` and `offset` instead of downloading full arrays. Provide `apply_patch` diffs for backend and templates, and commands to test paging (curl + browser)."

Files to change:
- `routes/admin.py` (handlers for payments, users, reports, work-keywords)
- `templates/admin/manage_payments.html`, `manage_users.html`, `dashboard.html`, `manage_work_keywords.html`

Tests:
- Seed DB with >100 items and verify page 1 and page 2 differ and `total` matches DB count.
- Inspect network panel to ensure only `limit` items returned.

Acceptance: paged endpoints return bounded lists and admin UI navigates between pages without fetching full DB.

---

## Phase 5 — Safe Refactors & Remove Technical Debt
Goal: Replace inline `onclick='openEditModal(JSON.stringify(obj))'` patterns, centralize shared utilities, and sweep for insecure stringification/XSS vectors.

Assistant Prompt (Phase 5):
- "Refactor all admin templates to avoid inline JSON-in-onclick. Replace with `data-item-id` attributes and a single delegated event listener that looks up the item from a page-level `allItems` map. Produce incremental `apply_patch` diffs for one template at a time (start with `manage_industries.html`). Also add a small lint-scan `grep` that finds `onclick=\'openEditModal(` and `JSON.stringify` occurrences."

Files to change (examples):
- All `templates/admin/*.html` where inline JSON is used (degrees, majors, industries, universities, projects)

Tests:
- Edit an item name containing an apostrophe (e.g., "McDonald's") and verify the edit modal opens and doesn't break HTML.

Acceptance: No inline JSON attributes remain; modal edit works for items with quotes or special characters.

---

## Phase 6 — QA, Monitoring & Rollout
Goal: Run full QA, remove debug logging, and prepare deployment/rollback steps.

Assistant Prompt (Phase 6):
- "Run through a QA checklist: smoke test all admin pages (create/edit/delete for degrees, majors, industries, payments export, audit log). Remove any temporary `console.log` and ensure serializer safe-access is used consistently. Provide a small PR description and a rollback plan (commit hashes and commands)."

QA checklist (short):
- Clear browser cache and verify modals populate correctly on cold load.
- Verify `/api/admin/*` endpoints return JSON and 200.
- Confirm no uncaught exceptions in server logs when loading admin pages.
- Verify pagination for `payments` and `users` works for large datasets.

Rollback commands examples:

```bash
# revert the last commit
git revert HEAD
# or reset to known good commit
git reset --hard <commit-hash>
```

---

## Templates: Useful agent prompts (copy-paste)

- Inspect repo for dropdown bugs:
  "List all templates and JS functions that call `/api/admin/departments` or `/api/admin/majors`. For each file, show the function name and the line numbers where the API is called."

- Make a minimal frontend patch:
  "Edit `templates/admin/manage_majors.html` to add a `refreshAddMajorDepartments()` function that is called from `openAddMajorModal()` and from the degree `<select>` change handler. Only modify this file and include the exact patch."

- Fix unsafe serializer access:
  "In `routes/admin.py`, replace direct `doc.logo` accesses with `getattr(doc, 'logo', '')` and run a quick grep to find other direct attribute reads. Return a patch and the grep results."

---

## Acceptance Criteria (Project-level)
- Dependent dropdowns populate reliably on modal open and on selecting parent value.
- No server 500 errors caused by serializers accessing missing attributes.
- Large admin lists use pagination or a documented browser-cap strategy.
- Inline JSON in `onclick` attributes is removed (prevent XSS & broken HTML).

---

## Notes & Hints
- The repo uses a custom `mongoengine.py` adapter that raises `AttributeError` for missing attributes; prefer `getattr()` in serializers.
- During fixes, prefer small localized `apply_patch` changes rather than sweeping refactors in a single PR.
- Keep debug logs short and remove them before final QA.

---

## Next steps (suggested immediate actions)
1. Run Phase 1 prompt with the assistant and paste the results here.
2. After triage, run Phase 2 prompt to patch `manage_majors.html` and validate in browser.
3. Continue through phases 3–6 as tests pass.

---

Generated by the assistant to coordinate staged admin fixes.

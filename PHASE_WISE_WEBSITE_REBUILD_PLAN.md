# ReportGen Website Rebuild Plan (Phase Wise, Small Tasks)

## 1) Current State Summary

This plan is based on the current codebase status and recent implementation work.

What is already done:
- Resume Builder UI has been redesigned across major steps.
- Mobile preview clutter was reduced and switched to a single preview action.
- SEO Phase 1 base setup is in place:
  - Custom error pages exist.
  - Global SEO blocks are added in shared templates.
  - robots.txt and sitemap.xml routes are implemented.
  - Favicon and social image assets are added.
- Public/legal pages are created and routed:
  - /privacy
  - /terms
  - /refund
  - /about
  - /contact
  - /faq
- Footer legal/resource links are now mapped to actual routes.

What is still weak:
- Information architecture is not strong enough from a user navigation perspective.
- Public-page discoverability relies too much on footer links.
- Contact flow is currently visual-only (no real submit handling).
- Landing page has high visual ambition but conversion clarity is not strong enough.
- UX consistency and trust details are not fully production-grade.

Reality check score (current):
- Visual ambition: good
- Conversion clarity: medium-low
- Trust and support UX: medium-low
- Product maturity for SaaS: draft stage, not final stage

## 2) Target Outcome

Goal:
Create a conversion-focused, trust-strong, clear SaaS website flow where users can quickly understand value, navigate key pages, and take action.

Primary business outcomes:
- Increase trial or first-action conversions from landing page.
- Reduce confusion in navigation.
- Increase trust signals for students and parents.
- Make support and legal flows feel complete and real.

User outcomes:
- User instantly understands what ReportGen does.
- User can reach report generation or resume builder in 1 to 2 clicks.
- User can discover FAQ, contact, legal, and about pages naturally.

## 3) Working Rules For All Phases

- Do not break existing backend routes or student/admin flows.
- Keep visual language consistent with current dark premium theme.
- Prefer incremental changes with measurable acceptance checks.
- Complete one phase fully before moving to next.
- Every phase ends with:
  - Code review
  - Basic device responsiveness check
  - Route and template verification

## 4) Phase Map Overview

- Phase 0: Audit and Baseline Freeze
- Phase 1: IA and Navigation Re-Architecture
- Phase 2: Landing Conversion Reframe
- Phase 3: Trust Layer and Content Credibility
- Phase 4: Legal and Support Completion
- Phase 5: Contact System Real Backend Flow
- Phase 6: Performance and Accessibility Hardening
- Phase 7: SEO and Discoverability Deepening
- Phase 8: Resume Builder UX Tightening (public to product bridge)
- Phase 9: QA, Analytics, and Launch Checklist

## 5) Detailed Phase Breakdown

---

## Phase 0: Audit and Baseline Freeze

Objective:
Capture current status and create a stable baseline before major visual or structural work.

Small tasks:
- List all public routes and verify they render without template errors.
- Capture current landing sections and navigation map.
- Record all known UX issues (navigation, trust, conversion, readability).
- Freeze current state in a checkpoint document.

Deliverables:
- Baseline audit report markdown.
- Route checklist with pass/fail.

Acceptance criteria:
- All public routes load successfully.
- Known issues are documented and prioritized.

Suggested prompt for this phase:
"Run Phase 0 now. Create a baseline audit with route health, landing structure map, and prioritized UX issues. Do not redesign yet."

---

## Phase 1: IA and Navigation Re-Architecture

Objective:
Make navigation obvious and complete so users can discover all key pages from top-level structures.

Small tasks:
- Define final top navigation items for public site.
- Add clear Support or Resources entry in top nav.
- Add legal access path outside footer (header menu or dedicated support page).
- Add active-state logic for public pages.
- Ensure mobile nav includes same destinations.
- Validate no dead links across nav and footer.

Deliverables:
- Updated navbar partial structure.
- Updated mobile menu structure.
- Navigation map diagram in markdown.

Acceptance criteria:
- User can reach About, FAQ, Contact, Privacy, Terms, Refund without hunting.
- No critical page is discoverable only from footer.

Suggested prompt for this phase:
"Implement Phase 1 IA and navigation re-architecture. Make public page discoverability clear on desktop and mobile."

---

## Phase 2: Landing Conversion Reframe

Objective:
Shift landing page from visual-heavy to conversion-strong while preserving premium look.

Small tasks:
- Rewrite hero hierarchy:
  - Strong headline
  - One-line value proposition
  - Primary CTA
  - Secondary CTA
- Add clearer proof strip near hero (universities, user counts, outcomes).
- Simplify section sequence to a conversion-friendly order.
- Reduce decorative motion where it hurts readability.
- Ensure CTA repeat at strategic points.

Deliverables:
- New section order spec.
- Updated hero and CTA blocks.

Acceptance criteria:
- First screen communicates product and action within 3 seconds.
- CTA is visible without scroll on common laptop viewport.

Suggested prompt for this phase:
"Implement Phase 2 landing conversion reframe with stronger hero clarity, proof-first sequencing, and cleaner CTA flow."

---

## Phase 3: Trust Layer and Content Credibility

Objective:
Strengthen trust so users feel safe to sign up, pay, and submit academic content.

Small tasks:
- Normalize brand identity details across all pages.
- Add credibility blocks:
  - University coverage proof
  - Security statements
  - Data privacy confidence copy
- Add realistic testimonials or case style format placeholders.
- Add transparent policy snippets linking to legal pages.

Deliverables:
- Trust section components.
- Content consistency pass document.

Acceptance criteria:
- No conflicting support email, phone, or identity details.
- Trust claims are specific and consistent.

Suggested prompt for this phase:
"Run Phase 3 trust layer improvements. Normalize brand details and add concrete credibility components across public pages."

---

## Phase 4: Legal and Support Completion

Objective:
Make legal and support ecosystem complete, scannable, and user-friendly.

Small tasks:
- Add legal index or support center page linking all legal/support docs.
- Add quick in-page TOC for long legal pages.
- Add last-updated and contact consistency checks.
- Ensure legal pages are readable on mobile (spacing and typography pass).

Deliverables:
- Legal hub structure.
- Updated legal templates with scannability features.

Acceptance criteria:
- User can find every legal page in max 2 clicks.
- Legal pages are scannable, not only long text walls.

Suggested prompt for this phase:
"Implement Phase 4 legal and support completion with a legal hub and better scannability."

---

## Phase 5: Contact System Real Backend Flow

Objective:
Convert contact from mock UX to real support workflow.

Small tasks:
- Define backend contact endpoint and input validation.
- Store submissions in DB or send via configured email pipeline.
- Add success and failure states based on real API response.
- Add anti-spam minimum controls.
- Log contact events for support follow-up.

Deliverables:
- Working contact API route.
- Contact form connected to backend.

Acceptance criteria:
- Contact form actually submits data and can be tracked.
- User sees true status, not fake success.

Suggested prompt for this phase:
"Implement Phase 5 by wiring contact form to a real backend endpoint with validation and true success/failure handling."

---

## Phase 6: Performance and Accessibility Hardening

Objective:
Improve speed, stability, and usability across devices.

Small tasks:
- Audit heavy CSS and motion effects on landing.
- Reduce unnecessary animations and repaints.
- Add reduced-motion behavior.
- Verify color contrast and keyboard access for nav and key CTA.
- Ensure form labels and focus states are accessible.

Deliverables:
- Performance and accessibility fixes.
- Before/after checklist.

Acceptance criteria:
- No major jank on mid-range mobile devices.
- Core navigation and form interactions are keyboard accessible.

Suggested prompt for this phase:
"Run Phase 6 performance and accessibility hardening without changing product behavior."

---

## Phase 7: SEO and Discoverability Deepening

Objective:
Move from foundation SEO to scalable SEO.

Small tasks:
- Validate canonical consistency across public pages.
- Add per-page rich meta where missing.
- Add structured data for organization and FAQ where relevant.
- Verify sitemap includes all valid indexable pages.
- Validate robots policy against business goals.

Deliverables:
- SEO deepening updates.
- SEO validation report.

Acceptance criteria:
- All public pages have appropriate metadata.
- Structured data is valid on key pages.

Suggested prompt for this phase:
"Implement Phase 7 SEO deepening with structured data and metadata quality improvements."

---

## Phase 8: Resume Builder UX Tightening

Objective:
Align product UX with improved marketing promise.

Small tasks:
- Ensure builder entry from landing is clear and expectation-setting.
- Remove residual clutter and polish step transitions.
- Improve save, preview, and completion feedback states.
- Ensure mobile usability on the full builder flow.

Deliverables:
- Builder UX polish updates.
- User flow consistency notes.

Acceptance criteria:
- User can start and finish core resume flow with low confusion.
- UI hierarchy remains clean on mobile.

Suggested prompt for this phase:
"Implement Phase 8 Resume Builder UX tightening to align product flow with new public-site messaging."

---

## Phase 9: QA, Analytics, and Launch Checklist

Objective:
Finalize quality, instrumentation, and rollout readiness.

Small tasks:
- Route and template regression pass.
- Cross-device smoke tests for top pages.
- Add event tracking for critical CTA and contact actions.
- Final content and spelling consistency pass.
- Prepare rollback-safe release checklist.

Deliverables:
- QA signoff checklist.
- Launch readiness report.

Acceptance criteria:
- No P1 issues open.
- Critical conversion events are trackable.

Suggested prompt for this phase:
"Run Phase 9 launch hardening with QA checklist, tracking instrumentation, and final signoff report."

## 6) Priority Sequence (If You Want Fast Wins)

Fastest high-impact order:
1. Phase 1 (Navigation IA)
2. Phase 2 (Landing conversion clarity)
3. Phase 5 (Real contact backend)
4. Phase 3 (Trust layer)
5. Phase 6 (Performance and accessibility)
6. Phase 4, 7, 8, 9

## 7) Definition of Done (Global)

A phase is done only if:
- Implementation is complete.
- No introduced syntax errors.
- Route-level behavior is verified.
- Mobile and desktop sanity checks pass.
- Notes are updated in a phase log.

## 8) Copy-Paste Prompt Sequence You Can Send Me One By One

Prompt 1:
"Start Phase 0 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 2:
"Start Phase 1 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 3:
"Start Phase 2 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 4:
"Start Phase 3 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 5:
"Start Phase 4 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 6:
"Start Phase 5 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 7:
"Start Phase 6 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 8:
"Start Phase 7 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 9:
"Start Phase 8 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

Prompt 10:
"Start Phase 9 from PHASE_WISE_WEBSITE_REBUILD_PLAN.md. Complete all small tasks and share outputs."

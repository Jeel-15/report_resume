External integrations (what the code uses)

- Email/SMS
  - SMTP for OTPs and registration emails (`routes/auth.py`), configured via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM_EMAIL`, `SMTP_USE_SSL`.
  - Evidence: `routes/auth.py` (`_send_register_otp_email`, `_send_reset_otp_email`).

- Auth
  - JWT tokens for API auth (`PyJWT`, env `JWT_SECRET`).
  - Google Sign-In optional integration (`google-auth` usage guarded in `routes/auth.py`).
  - Evidence: `routes/auth.py`, `requirements.txt`.

- AI / external APIs
  - `openai` referenced in `requirements.txt`; AI prompts exist in `routes/student.py` (server-side prompt templates). Confirm API usage and keys are set via environment.
  - Evidence: `requirements.txt`, `routes/student.py`.

- Browser automation / PDF generation
  - `playwright` in `requirements.txt` and `utils/pdf.py` suggests headless Chromium is used for PDF rendering/testing.
  - Evidence: `requirements.txt`, `utils/pdf.py` (review recommended).

- Payments
  - There is a `models/payment.py` and `routes/payment`-like references; provider details not found in repo — mark as [ASK USER].
  - Evidence: `models/payment.py` (exists), no live provider config discovered.

[ASK USER]
3) Confirm which payment provider (if any) is configured for production and where credentials are stored.

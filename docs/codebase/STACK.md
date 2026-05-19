Project stack (core)

- Python: [TODO] exact supported version not declared in repo (likely 3.8+)
- Web framework: Flask (3.0.3)
- Persistence: custom SQLite-backed shim exposing a mongoengine-like API (module: mongoengine.py)
- Dependencies (verifiable): see evidence below (from `requirements.txt`)
  - Flask==3.0.3
  - pymongo==4.6.3
  - python-dotenv==1.0.1
  - Flask-Limiter==3.8.0
  - playwright==1.42.0
  - openai (openai>=1.0.0)
  - bcrypt, PyJWT, Pillow, requests, pypdf, bleach, google-auth, openpyxl

Runtime notes
- App entrypoint: `app.py` launches Flask (development mode by default).
- Database: application uses `mongoengine.connect(path=...)` which maps to `mongoengine.py` and stores documents in a local SQLite file (default `data/app.db`).

Evidence
- `requirements.txt` (dependency pins)
- `app.py` (Flask app, connect(path=...))
- `mongoengine.py` (SQLite-backed store and ORM shim)
- `routes/auth.py` (JWT, bcrypt, SMTP usage)

[ASK USER]
1) Confirm the supported Python runtime (3.8/3.9/3.10/3.11) so I can document precisely.

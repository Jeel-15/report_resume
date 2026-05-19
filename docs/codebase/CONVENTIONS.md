Conventions (observed)

- Python files: modules grouped by feature (routes, models, utils).
- Flask: Blueprints registered in `app.py` and mounted under `/api/*` prefixes.
- Models: `models/*.py` define Document-style classes consumed via `mongoengine.py` compatibility layer.
- Environment: `python-dotenv` is used and secrets/keys come from environment variables (`.env`) — code reads `JWT_SECRET`, `SQLITE_PATH`, SMTP_* and other vars.
- Template conventions: Jinja2 templates inside `templates/` with partials under `templates/partials/` and admin/student folders.
- Static assets: `static/css`, `static/js`, `static/images`; runtime uploads under `static/uploads` and `uploads/`.

Evidence
- `app.py`, `routes/*.py`, `models/*`
- `python-dotenv` in `requirements.txt` and `load_dotenv()` in `app.py`
- `templates/` folder structure and `templates/partials/`

[TODO]
- Add lint/format rules (no `pyproject.toml` or lint config found).
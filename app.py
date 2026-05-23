import os
import datetime
from flask import Flask, jsonify, render_template, send_from_directory
import markdown as _markdown
from dotenv import load_dotenv
from mongoengine import connect

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'fallback_secret')
report_description_mode = str(os.getenv('REPORT_DESCRIPTION_MODE', 'hybrid') or 'hybrid').strip().lower()
if report_description_mode not in {'legacy', 'hybrid', 'keywords_only'}:
    report_description_mode = 'hybrid'
app.config['REPORT_DESCRIPTION_MODE'] = report_description_mode
app.config['SQLITE_PATH'] = os.getenv(
    'SQLITE_PATH',
    os.path.join(app.root_path, 'data', 'app.db')
)
os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'report_images'), exist_ok=True)
os.makedirs(os.path.dirname(app.config['SQLITE_PATH']), exist_ok=True)

# Initialize local SQLite-backed data layer
try:
    connect(path=app.config['SQLITE_PATH'])
except Exception as e:
    import sys
    print(f"[CRITICAL] Database connection failed: {e}", file=sys.stderr)
    raise

from routes.auth import auth_bp, limiter
limiter.init_app(app)
app.register_blueprint(auth_bp, url_prefix='/api/auth')

from routes.admin import admin_bp
app.register_blueprint(admin_bp, url_prefix='/api/admin')

from routes.bulk_import import bulk_import_bp
app.register_blueprint(bulk_import_bp, url_prefix='/api/admin/bulk-import')

from routes.student import student_bp
app.register_blueprint(student_bp, url_prefix='/api/student')

from routes.reports import reports_bp
app.register_blueprint(reports_bp, url_prefix='/api/reports')

from routes.upload import upload_bp
app.register_blueprint(upload_bp, url_prefix='/api/upload')

from routes.internship_types import internship_types_bp
app.register_blueprint(internship_types_bp, url_prefix='/api/internship-types')

from routes.pages import pages_bp
app.register_blueprint(pages_bp)


@app.context_processor
def utility_processor():
    def last_updated(template_name: str) -> str:
        try:
            # Resolve template path relative to app root
            tpl = template_name if template_name.endswith('.html') else f"{template_name}.html"
            tpl_path = os.path.join(app.root_path, 'templates', tpl)
            if not os.path.exists(tpl_path):
                return datetime.date.today().strftime('%B %d, %Y')
            mtime = os.path.getmtime(tpl_path)
            return datetime.date.fromtimestamp(mtime).strftime('%B %d, %Y')
        except Exception:
            return datetime.date.today().strftime('%B %d, %Y')

    return dict(last_updated=last_updated)


@app.template_filter('markdown')
def markdown_filter(text):
    return _markdown.markdown(str(text or ''), extensions=['extra', 'sane_lists'])


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template('404.html'), 403


@app.get('/api/health')
def health():
    return jsonify({'status': 'OK'})


@app.get('/uploads/<path:filename>')
def uploads(filename):
    base_dirs = [
        os.path.join(os.path.dirname(__file__), 'static', 'uploads'),
        os.path.join(os.path.dirname(__file__), 'uploads'),
    ]

    for base_dir in base_dirs:
        candidate = os.path.join(base_dir, filename)
        if os.path.exists(candidate):
            return send_from_directory(base_dir, filename)

    return send_from_directory(base_dirs[0], filename)


# Startup diagnostics
print("[STARTUP] All blueprints registered successfully")
student_routes = [str(rule) for rule in app.url_map.iter_rules() if 'student' in str(rule)]
if student_routes:
    print(f"[STARTUP] Registered student routes: {', '.join(student_routes)}")
else:
    print("[STARTUP] WARNING: No student routes registered!")

if __name__ == '__main__':
    # Default port is 5000, configurable via PORT environment variable
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

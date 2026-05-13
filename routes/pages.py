import os
import re
from flask import Blueprint, render_template
from models.user import User
from models.report import Report
from models.video_guide import VideoGuide

pages_bp = Blueprint('pages', __name__)

def get_sidebar_counts():
    """Get counts for sidebar badges"""
    try:
        student_count = User.objects(role='student').count()
        report_count = Report.objects().count()
        return {
            'student_count': student_count,
            'report_count': report_count
        }
    except:
        return {
            'student_count': 0,
            'report_count': 0
        }


def _extract_youtube_id(url):
    value = str(url or '').strip()
    if not value:
        return ''
    match = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})', value)
    return match.group(1) if match else ''


def _serialize_public_video_guide(doc):
    video_type = str(getattr(doc, 'videoType', 'youtube') or 'youtube').strip().lower() or 'youtube'
    video_url = str(getattr(doc, 'videoUrl', '') or '').strip()
    embed_url = video_url
    if video_type == 'youtube':
        youtube_id = _extract_youtube_id(video_url)
        if youtube_id:
            embed_url = f'https://www.youtube.com/embed/{youtube_id}'
    return {
        'id': str(getattr(doc, 'id', '') or ''),
        'title': getattr(doc, 'title', '') or 'Untitled video',
        'description': getattr(doc, 'description', '') or '',
        'videoType': video_type,
        'videoUrl': video_url,
        'embedUrl': embed_url,
        'sortOrder': getattr(doc, 'sortOrder', 0) or 0,
    }


def _get_public_video_guides(limit=4):
    try:
        docs = [doc for doc in VideoGuide.objects().order_by('sortOrder') if bool(getattr(doc, 'isActive', True))]
    except Exception:
        docs = []
    return [_serialize_public_video_guide(doc) for doc in docs[:limit]]

@pages_bp.route('/')
def home():
    # Typically would redirect to /login or student dashboard
    return render_template('landing.html', public_video_guides=_get_public_video_guides())

@pages_bp.route('/login')
def login():
    return render_template(
        'login.html',
        google_client_id=os.getenv('GOOGLE_CLIENT_ID', '').strip(),
        hide_navbar=True
    )


@pages_bp.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html', hide_navbar=True)

@pages_bp.route('/register')
def register():
    return render_template('register.html', hide_navbar=True)

@pages_bp.route('/admin/dashboard')
def admin_dashboard():
    counts = get_sidebar_counts()
    return render_template('admin/dashboard.html', **counts)

@pages_bp.route('/admin/majors')
def admin_majors():
    counts = get_sidebar_counts()
    return render_template('admin/manage_majors.html', **counts)


@pages_bp.route('/admin/project-titles')
def admin_project_titles():
    counts = get_sidebar_counts()
    return render_template('admin/manage_project_titles.html', active_page='project_titles', **counts)


@pages_bp.route('/admin/career-objectives')
def admin_career_objectives():
    counts = get_sidebar_counts()
    return render_template('admin/manage_career_objectives.html', active_page='career_objectives', **counts)


@pages_bp.route('/admin/resume-keywords')
def admin_resume_keywords():
    counts = get_sidebar_counts()
    return render_template('admin/manage_resume_keywords.html', active_page='resume_keywords', **counts)

@pages_bp.route('/admin/report-sections')
def admin_report_sections():
    counts = get_sidebar_counts()
    return render_template('admin/manage_report_sections.html', active_page='report_sections', **counts)

@pages_bp.route('/admin/departments')
def admin_departments():
    counts = get_sidebar_counts()
    return render_template('admin/manage_departments.html', active_page='departments', **counts)

@pages_bp.route('/admin/work-keywords')
def admin_work_keywords():
    counts = get_sidebar_counts()
    return render_template('admin/manage_work_keywords.html', active_page='work-keywords', **counts)

@pages_bp.route('/admin/users')
def admin_users():
    counts = get_sidebar_counts()
    return render_template('admin/manage_users.html', **counts)

@pages_bp.route('/admin/degrees')
def admin_degrees():
    counts = get_sidebar_counts()
    return render_template('admin/manage_degrees.html', **counts)

@pages_bp.route('/admin/universities')
def admin_universities():
    counts = get_sidebar_counts()
    return render_template('admin/manage_universities.html', **counts)

@pages_bp.route('/admin/colleges')
def admin_colleges():
    counts = get_sidebar_counts()
    return render_template('admin/manage_colleges.html', **counts)

@pages_bp.route('/admin/industries')
def admin_industries():
    counts = get_sidebar_counts()
    return render_template('admin/manage_industries.html', **counts)

@pages_bp.route('/admin/services')
def admin_services():
    counts = get_sidebar_counts()
    return render_template('admin/manage_services.html', **counts)

@pages_bp.route('/admin/payments')
def admin_payments():
    counts = get_sidebar_counts()
    return render_template('admin/manage_payments.html', **counts)

@pages_bp.route('/admin/reports')
def admin_reports():
    counts = get_sidebar_counts()
    return render_template('admin/manage_reports.html', **counts)


@pages_bp.route('/admin/report/<report_id>')
def admin_report_view(report_id):
    counts = get_sidebar_counts()
    return render_template('admin/report_view.html', report_id=report_id, active_page='reports', **counts)

@pages_bp.route('/admin/types')
def admin_types():
    counts = get_sidebar_counts()
    return render_template('admin/manage_types.html', active_page='internship_types', **counts)

@pages_bp.route('/admin/settings')
def admin_settings():
    counts = get_sidebar_counts()
    return render_template('admin/settings.html', **counts)


@pages_bp.route('/admin/notifications')
def admin_notifications():
    counts = get_sidebar_counts()
    return render_template('admin/notifications.html', active_page='notifications', **counts)

@pages_bp.route('/admin/bulk-import')
def admin_bulk_import():
    counts = get_sidebar_counts()
    return render_template('admin/manage_bulk_import.html', **counts)

@pages_bp.route('/student/dashboard')
def student_dashboard():
    return render_template('student/dashboard.html')

@pages_bp.route('/student/profile')
def student_profile():
    return render_template('student/profile.html')

@pages_bp.route('/student/create')
def student_create():
    return render_template('student/create_report.html')


@pages_bp.route('/student/resumes')
def student_resumes():
    return render_template('student/resumes.html')


@pages_bp.route('/student/resume/builder')
def student_resume_builder():
    return render_template('student/resume_builder.html')


@pages_bp.route('/student/resume/<resume_id>/builder')
def student_resume_builder_edit(resume_id):
    return render_template('student/resume_builder.html', resume_id=resume_id)

@pages_bp.route('/student/report/<report_id>')
def student_report_view(report_id):
    return render_template('student/report_view.html', admin_readonly=False)


@pages_bp.route('/admin/audit-log')
def admin_audit_log():
    counts = get_sidebar_counts()
    return render_template('admin/audit_log.html', active_page='audit_log', **counts)


@pages_bp.route('/admin/video-guides')
def admin_video_guides():
    counts = get_sidebar_counts()
    return render_template('admin/manage_video_guides.html', active_page='video_guides', **counts)


@pages_bp.route('/logout')
def logout_page():
    return render_template('logout.html')

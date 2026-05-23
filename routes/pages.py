import os
import re
import datetime
from flask import Blueprint, Response, render_template, request
from flask import jsonify
from models.user import User
from models.report import Report
from models.resume import Resume
from models.video_guide import VideoGuide
from models.contact_submission import ContactSubmission
from models.blog_post import BlogPost
from models.faq_item import FaqItem

pages_bp = Blueprint('pages', __name__)

def get_sidebar_counts():
    """Get counts for sidebar badges"""
    try:
        student_count = User.objects(role='student').count()
        report_count = Report.objects().count()
        resume_count = Resume.objects().count()
        return {
            'student_count': student_count,
            'report_count': report_count,
            'resume_count': resume_count,
        }
    except:
        return {
            'student_count': 0,
            'report_count': 0,
            'resume_count': 0,
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


def _get_public_faqs():
    """Get active FAQ items grouped by category for the public FAQ page."""
    try:
        docs = list(FaqItem.objects(isActive=True).order_by('category', 'sortOrder'))
    except Exception:
        docs = []
    result = {}
    for doc in docs:
        cat = str(getattr(doc, 'category', 'General') or 'General')
        if cat not in result:
            result[cat] = []
        result[cat].append({
            'question': getattr(doc, 'question', ''),
            'answer': getattr(doc, 'answer', ''),
        })
    return result

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


@pages_bp.route('/admin/assignments')
def admin_assignments():
    counts = get_sidebar_counts()
    return render_template('admin/manage_assignments.html', active_page='assignments', **counts)


@pages_bp.route('/admin/assignment-prompts')
def admin_assignment_prompts():
    counts = get_sidebar_counts()
    return render_template('admin/manage_assignment_prompts.html', active_page='assignment_prompts', **counts)


@pages_bp.route('/admin/resumes')
def admin_resumes():
    counts = get_sidebar_counts()
    return render_template('admin/manage_resumes.html', active_page='resume_tracking', **counts)

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


@pages_bp.route('/student/assignments')
def student_assignments():
    """My Assignments list page."""
    return render_template('student/assignments.html')


@pages_bp.route('/student/assignments/new')
def student_assignment_new():
    """Create new assignment — redirects to studio with type selection."""
    return render_template('student/assignment_studio.html', session_id=None)


@pages_bp.route('/student/assignments/<session_id>')
def student_assignment_studio(session_id):
    """Assignment Studio workspace for an existing session."""
    return render_template('student/assignment_studio.html', session_id=session_id)

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


@pages_bp.route('/admin/blog')
def admin_blog():
    counts = get_sidebar_counts()
    return render_template('admin/manage_blog.html', active_page='blog', **counts)


@pages_bp.route('/admin/faq')
def admin_faq():
    counts = get_sidebar_counts()
    return render_template('admin/manage_faq.html', active_page='faq', **counts)


@pages_bp.route('/logout')
def logout_page():
    return render_template('logout.html')


@pages_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')


@pages_bp.route('/terms')
def terms():
    return render_template('terms.html')


@pages_bp.route('/refund')
def refund():
    return render_template('refund.html')


@pages_bp.route('/about')
def about():
    return render_template('about.html')


@pages_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    contact_values = {
        'name': '',
        'email': '',
        'subject': '',
        'message': '',
    }
    contact_error = ''
    contact_success = False

    if request.method == 'POST':
        contact_values = {
            'name': str(request.form.get('name', '') or '').strip(),
            'email': str(request.form.get('email', '') or '').strip(),
            'subject': str(request.form.get('subject', '') or '').strip(),
            'message': str(request.form.get('message', '') or '').strip(),
        }

        subject_labels = {
            'report-issue': 'Report Generation Issue',
            'resume-issue': 'Resume Builder Issue',
            'account': 'Account / Login',
            'payment': 'Payment / Billing',
            'university': 'University Not Listed',
            'other': 'Other',
        }

        if not all(contact_values.values()):
            contact_error = 'Please complete every field before sending the message.'
        elif '@' not in contact_values['email']:
            contact_error = 'Please enter a valid email address.'
        elif contact_values['subject'] not in subject_labels:
            contact_error = 'Please choose a support topic.'
        else:
            try:
                contact_request = ContactSubmission(
                    name=contact_values['name'],
                    email=contact_values['email'],
                    subject=subject_labels[contact_values['subject']],
                    subjectKey=contact_values['subject'],
                    message=contact_values['message'],
                    ipAddress=str(request.headers.get('X-Forwarded-For', request.remote_addr or '') or '').split(',')[0].strip(),
                    userAgent=str(request.headers.get('User-Agent', '') or '').strip(),
                )
                contact_request.save()
                contact_success = True
                contact_values = {
                    'name': '',
                    'email': '',
                    'subject': '',
                    'message': '',
                }
            except Exception:
                contact_error = 'We could not save your message right now. Please email support@reportgen.in.'

    return render_template(
        'contact.html',
        contact_values=contact_values,
        contact_error=contact_error,
        contact_success=contact_success,
    )


@pages_bp.route('/blog')
def blog():
    """Blog listing page showing published blog posts."""
    try:
        posts = list(BlogPost.objects(isPublished=True).order_by('-publishedAt'))
    except Exception:
        posts = []
    serialized = []
    for p in posts:
        serialized.append({
            'title':      getattr(p, 'title', ''),
            'slug':       getattr(p, 'slug', ''),
            'excerpt':    getattr(p, 'excerpt', ''),
            'coverImage': getattr(p, 'coverImage', ''),
            'tags':       list(getattr(p, 'tags', []) or []),
            'author':     getattr(p, 'author', 'ReportGen Team'),
            'publishedAt': p.publishedAt.strftime('%b %d, %Y') if getattr(p, 'publishedAt', None) else '',
        })
    return render_template('blog.html', posts=serialized)


@pages_bp.route('/blog/<slug>')
def blog_post(slug):
    """Single blog post page."""
    try:
        post = BlogPost.objects(slug=slug, isPublished=True).first()
    except Exception:
        post = None
    if not post:
        from flask import abort
        abort(404)
    return render_template('blog_post.html', post={
        'title':      getattr(post, 'title', ''),
        'slug':       getattr(post, 'slug', ''),
        'excerpt':    getattr(post, 'excerpt', ''),
        'content':    getattr(post, 'content', ''),
        'coverImage': getattr(post, 'coverImage', ''),
        'tags':       list(getattr(post, 'tags', []) or []),
        'author':     getattr(post, 'author', 'ReportGen Team'),
        'publishedAt': post.publishedAt.strftime('%B %d, %Y') if getattr(post, 'publishedAt', None) else '',
    })


@pages_bp.route('/faq')
def faq():
    """FAQ page with dynamic content from database."""
    faq_data = _get_public_faqs()
    return render_template('faq.html', faq_data=faq_data)


@pages_bp.route('/api/contact', methods=['POST'])
def api_contact():
    """AJAX endpoint to accept contact submissions. Returns JSON."""
    data = {}
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = {k: request.form.get(k, '') for k in ('name', 'email', 'subject', 'message')}

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    subject_key = (data.get('subject') or '').strip()
    message = (data.get('message') or '').strip()

    allowed_subjects = {'report-issue', 'resume-issue', 'account', 'payment', 'university', 'other'}

    # Basic validation
    errors = []
    if len(name) < 2:
        errors.append('Please provide your full name.')
    if '@' not in email or len(email) < 6:
        errors.append('Please provide a valid email address.')
    if subject_key not in allowed_subjects:
        errors.append('Please choose a support topic.')
    if len(message) < 10:
        errors.append('Please provide more details in your message (at least 10 characters).')

    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    # Anti-spam: minimal rate limiting per IP
    ip = str(request.headers.get('X-Forwarded-For', request.remote_addr or '') or '').split(',')[0].strip()
    try:
        last = ContactSubmission.objects(ipAddress=ip).order_by('-createdAt').first()
    except Exception:
        last = None

    import datetime
    now = datetime.datetime.utcnow()
    if last and getattr(last, 'createdAt', None):
        delta = now - last.createdAt
        if delta.total_seconds() < 60:
            return jsonify({'ok': False, 'errors': ['Please wait a minute before sending another message.']}), 429

    # Store submission
    try:
        contact_request = ContactSubmission(
            name=name,
            email=email,
            subject=subject_key if subject_key in allowed_subjects else 'other',
            subjectKey=subject_key,
            message=message,
            ipAddress=ip,
            userAgent=str(request.headers.get('User-Agent', '') or '').strip(),
            source='api-contact'
        )
        contact_request.save()
    except Exception as e:
        import logging
        logging.exception('Failed to save contact submission')
        return jsonify({'ok': False, 'errors': ['We could not save your message right now. Please email support@reportgen.in.']}), 500

    # TODO: enqueue email notification to support pipeline if configured

    # Log the event
    try:
        import logging
        logging.getLogger('contact').info('New contact submission', extra={'ip': ip, 'email': email, 'subject': subject_key})
    except Exception:
        pass

    return jsonify({'ok': True, 'message': 'Message received. We will respond within 24 hours.'}), 201


@pages_bp.route('/legal')
def legal_hub():
    return render_template('legal_hub.html')


@pages_bp.route('/robots.txt')
def robots_txt():
    content = """User-agent: *
Allow: /
Allow: /about
Allow: /faq
Allow: /blog
Allow: /blog/
Allow: /contact
Allow: /privacy
Allow: /terms
Allow: /refund
Disallow: /admin/
Disallow: /api/
Disallow: /student/
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /logout

Sitemap: https://reportgen.in/sitemap.xml
"""
    # expose legal hub for crawlers
    content = content.replace('Allow: /refund', 'Allow: /refund\nAllow: /legal')
    return Response(content.strip(), mimetype='text/plain')


@pages_bp.route('/sitemap.xml')
def sitemap_xml():
    today = datetime.date.today().isoformat()
    domain = 'https://reportgen.in'

    static_pages = [
        ('/', '1.0', 'weekly'),
        ('/about', '0.8', 'monthly'),
        ('/faq', '0.8', 'monthly'),
        ('/contact', '0.6', 'monthly'),
        ('/privacy', '0.3', 'yearly'),
        ('/terms', '0.3', 'yearly'),
        ('/refund', '0.3', 'yearly'),
        ('/legal', '0.4', 'yearly'),
        ('/blog', '0.9', 'daily'),
    ]

    urls = []
    for path, priority, freq in static_pages:
        urls.append(f"""    <url>
        <loc>{domain}{path}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>{freq}</changefreq>
        <priority>{priority}</priority>
    </url>""")

    try:
        from models.blog import BlogPost
        posts = list(BlogPost.objects(isPublished=True).order_by('-publishedAt'))
        for post in posts:
            slug = str(getattr(post, 'slug', '') or '')
            if slug:
                updated = getattr(post, 'updatedAt', None)
                lastmod = updated.date().isoformat() if updated else today
                urls.append(f"""    <url>
        <loc>{domain}/blog/{slug}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.7</priority>
    </url>""")
    except Exception:
        pass

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    return Response(xml, mimetype='application/xml')

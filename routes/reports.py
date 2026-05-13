import os
import shutil
import io
import uuid
import secrets
import re
import json
import html
import logging
import requests
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, render_template, send_file, send_from_directory, current_app
from routes.auth import token_required
from routes.upload import _delete_upload_file
from models.report import Report
from models.major import Major
from models.user import User
from models.industry import Industry
from models.college import College
from models.university import University
from utils.pdf import generate_pdf_from_html, _md_to_html
from utils.report_sections import resolve_effective_report_sections

reports_bp = Blueprint('reports', __name__)
REPORT_IMAGE_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'report_images')
logging.basicConfig(level=logging.DEBUG)


def _normalize_report_description_mode(value):
    mode = str(value or 'hybrid').strip().lower()
    return mode if mode in {'legacy', 'hybrid', 'keywords_only'} else 'hybrid'


def _get_report_description_mode():
    mode_from_config = current_app.config.get('REPORT_DESCRIPTION_MODE')
    if mode_from_config:
        return _normalize_report_description_mode(mode_from_config)
    return _normalize_report_description_mode(os.getenv('REPORT_DESCRIPTION_MODE', 'hybrid'))


def _normalize_keywords_list(value):
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(',')]
    elif isinstance(value, list):
        raw_items = [str(part).strip() for part in value]
    else:
        raw_items = []

    normalized = []
    seen = set()
    for item in raw_items:
        if not item:
            continue
        lowered = item.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(item)
    return normalized


def _detect_text_direction(text):
    """
    Detect if text is RTL (Arabic, Urdu, Hebrew, Persian).
    Returns 'rtl' or 'ltr'.
    Works universally — no language name needed.
    """
    if not text:
        return 'ltr'
    # RTL Unicode ranges:
    # Arabic: \u0600-\u06FF
    # Arabic Supplement: \u0750-\u077F  
    # Hebrew: \u0590-\u05FF
    # Arabic Presentation Forms: \uFB50-\uFDFF, \uFE70-\uFEFF
    rtl_pattern = re.compile(
        r'[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]'
    )
    # Count RTL vs total characters
    rtl_chars = len(rtl_pattern.findall(text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return 'ltr'
    # If more than 20% of characters are RTL → it's RTL text
    return 'rtl' if (rtl_chars / total_chars) > 0.2 else 'ltr'

def _humanize_key(key=''):
    return str(key).replace('_', ' ').replace('-', ' ').title()


def _to_object_if_json(value):
    if isinstance(value, str):
        raw = value.strip()
        if raw and (raw.startswith('{') or raw.startswith('[')):
            try:
                return json.loads(raw)
            except Exception:
                return value
    return value


def _normalize_section_text(value):
    """Normalize mixed text/HTML and keep only safe formatting tags."""
    text = '' if value is None else str(value)
    # Handle literal \n escape sequences (not real newlines) from JSON/webhook payloads
    text = text.replace('\\n', '\n')
    # Handle HTML-encoded br/p tags that bypass regex matching
    text = re.sub(r'&lt;br\s*/?&gt;', '\n', text)
    text = re.sub(r'&lt;/?p\s*&gt;', '\n\n', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Handle escaped/double-escaped payloads from webhook flows.
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded

    # Remove dangerous tags and their bodies.
    text = re.sub(r'(?is)<\s*(script|style|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>', '', text)
    text = re.sub(r'(?is)<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*\/?>', '', text)

    # Preserve only safe formatting tags for PDF rendering.
    allowed_tags = {
        'strong', 'em', 'b', 'i', 'u', 'ul', 'ol', 'li', 'p', 'br',
        'table', 'thead', 'tbody', 'tr', 'th', 'td', 'blockquote', 'code', 'pre'
    }

    def _strip_unsafe_tags(match):
        is_closing, tag = match.group(1), match.group(2).lower()
        if tag not in allowed_tags:
            return ''
        if tag == 'br':
            return '<br>'
        return f"</{tag}>" if is_closing else f"<{tag}>"

    text = re.sub(r'<\s*(/?)\s*([a-zA-Z0-9]+)(?:\s+[^>]*)?>', _strip_unsafe_tags, text)

    # Compact excessive blank lines while preserving paragraph breaks.
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _repair_markdown_numbering(text):
    """Fix common AI double-numbering pattern: '1. Title:' + '2. details...'"""
    if not text:
        return text

    lines = text.split('\n')
    repaired = []
    i = 0
    while i < len(lines):
        current = lines[i]
        current_match = re.match(r'^\s*(\d+)\.\s+(.+)$', current)
        if current_match and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_match = re.match(r'^\s*(\d+)\.\s+(.+)$', next_line)

            # Conservative rule: if current looks like a heading item and next item starts
            # with lowercase text, treat next as continuation text instead of separate item.
            if next_match:
                current_body = current_match.group(2).strip()
                next_body = next_match.group(2).strip()
                if current_body.endswith(':') and re.match(r'^[a-z]', next_body):
                    repaired.append(current)
                    repaired.append(f"   {next_body}")
                    i += 2
                    continue

        repaired.append(current)
        i += 1

    return '\n'.join(repaired)


def _split_content_for_middle_images(text):
    """Split section text into two parts so middle images can be inserted in-between."""
    if not text:
        return '', ''

    blocks = [b for b in text.split('\n\n') if b.strip()]
    if len(blocks) < 2:
        return text, ''

    mid = len(blocks) // 2
    before = '\n\n'.join(blocks[:mid]).strip()
    after = '\n\n'.join(blocks[mid:]).strip()
    return before, after


def _sanitize_content_map(content):
    if not isinstance(content, dict):
        return {}
    out = {}
    for key, value in content.items():
        skey = str(key)
        if skey.startswith('__'):
            out[skey] = value
        else:
            out[skey] = _normalize_section_text(value)
    return out


def _sanitize_titles_map(titles):
    if not isinstance(titles, dict):
        return {}
    out = {}
    for key, value in titles.items():
        out[str(key)] = _normalize_section_text(value)
    return out


def _normalize_asset_url(url, request):
    if not url or not isinstance(url, str):
        return ''
    if url.startswith('data:image/'):
        return url
    if url.startswith('http://') or url.startswith('https://'):
        return url

    # Always resolve report assets against the current request host.
    # This avoids stale BACKEND_URL values (for example expired ngrok URLs)
    # breaking image rendering inside PDF preview/download.
    base_backend_url = request.host_url.rstrip('/')
    if url.startswith('/'):
        return f"{base_backend_url}{url}"
    return f"{base_backend_url}/{url.lstrip('/')}"


def _resolve_public_base_url(request):
    request_backend_url = str(getattr(request, 'host_url', '') or '').rstrip('/')
    env_backend_url = str(os.getenv('BACKEND_URL', '')).strip().rstrip('/')

    if request_backend_url and not request_backend_url.startswith(('http://127.0.0.1', 'http://localhost')):
        return request_backend_url

    if env_backend_url:
        return env_backend_url

    return request_backend_url


def _resolve_cover_logos(content, report, request):
    raw_cover = content.get('__cover', {}) if isinstance(content, dict) else {}
    custom_logos = []

    if isinstance(raw_cover, dict):
        raw_custom = raw_cover.get('logos', [])
        if isinstance(raw_custom, list):
            custom_logos = [
                _normalize_asset_url(v, request)
                for v in raw_custom[:2]
                if isinstance(v, str) and v.strip()
            ]

    user_ref = getattr(report, 'user', None)
    user = None
    if user_ref is not None:
        if hasattr(user_ref, 'universityLogoOverride'):
            user = user_ref
        else:
            user_id = getattr(user_ref, 'id', None) or user_ref
            user = User.objects(id=user_id).first() if user_id else None

    university_override = str(getattr(user, 'universityLogoOverride', '') or '').strip() if user else ''
    college_override = str(getattr(user, 'collegeLogoOverride', '') or '').strip() if user else ''

    user_university_logo = str(getattr(getattr(user, 'university', None), 'logo', '') or '').strip() if user else ''
    user_college_logo = str(getattr(getattr(user, 'college', None), 'logo', '') or '').strip() if user else ''
    report_university_logo = str(getattr(report.university, 'logo', '') or '').strip() if getattr(report, 'university', None) else ''
    report_college_logo = str(getattr(report.college, 'logo', '') or '').strip() if getattr(report, 'college', None) else ''

    fallback_logos = [
        _normalize_asset_url(university_override or user_university_logo or report_university_logo, request),
        _normalize_asset_url(college_override or user_college_logo or report_college_logo, request),
    ]
    fallback_logos = [x for x in fallback_logos if x]

    logos = (custom_logos if custom_logos else fallback_logos)[:2]
    return logos


def _build_cover_page_html_from_blocks(blocks, font_size='12', font_family='Times New Roman', align='center', cover_logos=None):
    """Build cover page HTML from blocks array instead of using precomputed HTML"""
    if not isinstance(blocks, list) or not blocks:
        return ''

    def _cover_style_defaults(kind):
        key = str(kind or 'custom').lower()
        if key == 'title':
            return {'fontSize': '17', 'bold': True, 'italic': False}
        if key == 'subtitle':
            return {'fontSize': '14', 'bold': True, 'italic': False}
        if key == 'line':
            return {'fontSize': '12', 'bold': True, 'italic': False}
        if key == 'small':
            return {'fontSize': '10', 'bold': True, 'italic': False}
        if key == 'italic':
            return {'fontSize': '10', 'bold': False, 'italic': True}
        if key == 'logos':
            return {'fontSize': '12', 'bold': False, 'italic': False}
        return {'fontSize': '12', 'bold': False, 'italic': False}

    def _clamp_size(value, fallback='12'):
        text = str(value if value is not None else fallback).replace('pt', '').strip()
        try:
            parsed = int(round(float(text)))
        except Exception:
            try:
                parsed = int(round(float(str(fallback).replace('pt', '').strip())))
            except Exception:
                parsed = 12
        return str(max(8, min(32, parsed)))
    
    logos = cover_logos if isinstance(cover_logos, list) else []
    college_logo = str(logos[0]).strip() if len(logos) > 0 and logos[0] else ''
    university_logo = str(logos[1]).strip() if len(logos) > 1 and logos[1] else ''

    line_html = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        
        block_kind = str(block.get('kind', 'custom')).lower()
        block_value = str(block.get('value', '')).strip()
        defaults = _cover_style_defaults(block_kind)
        block_size = _clamp_size(block.get('fontSize'), defaults['fontSize'])
        block_bold = block.get('bold') if isinstance(block.get('bold'), bool) else defaults['bold']
        block_italic = block.get('italic') if isinstance(block.get('italic'), bool) else defaults['italic']
        style_attr = f' style="font-size:{block_size}pt;font-weight:{"700" if block_bold else "400"};font-style:{"italic" if block_italic else "normal"};"'
        escaped_value = block_value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')
        
        if block_kind == 'logos':
            line_html.append(f'''
                    <div class="cover-logo-row">
                        <div class="cover-logo-box">
                            {'<img src="' + college_logo + '" alt="College/Institute Logo">' if college_logo else '<div class="cover-logo-placeholder">College/Institute<br>Logo</div>'}
                        </div>
                        <div class="cover-logo-box">
                            {'<img src="' + university_logo + '" alt="University Logo">' if university_logo else '<div class="cover-logo-placeholder">University Logo</div>'}
                        </div>
                    </div>''')
        elif block_kind == 'title':
            line_html.append(f'<div class="cover-main-title"{style_attr}>{escaped_value or "&nbsp;"}</div>')
        elif block_kind == 'subtitle':
            line_html.append(f'<div class="cover-subtitle"{style_attr}>{escaped_value or "&nbsp;"}</div>')
        elif block_kind == 'line':
            line_html.append(f'<div class="cover-line"{style_attr}>{escaped_value or "&nbsp;"}</div>')
        elif block_kind == 'small':
            line_html.append(f'<div class="cover-line small"{style_attr}>{escaped_value or "&nbsp;"}</div>')
        elif block_kind == 'italic':
            line_html.append(f'<div class="cover-line italic"{style_attr}>{escaped_value or "&nbsp;"}</div>')
        elif block_kind == 'custom':
            escaped_with_br = escaped_value.replace('\n', '<br>')
            line_html.append(f'<div class="cover-custom-note"{style_attr}>{escaped_with_br or "&nbsp;"}</div>')
        else:
            line_html.append(f'<div class="cover-line"{style_attr}>{escaped_value or "&nbsp;"}</div>')
    
    html_lines = '\n'.join(line_html)
    return f'''
            <div style="font-family:{font_family}; text-align:{align}; line-height:1.5; color:#000;">
                {html_lines}
            </div>'''


def _resolve_cover_page(content, cover_logos=None):
    raw_cover_page = content.get('__coverPage', {}) if isinstance(content, dict) else {}
    if isinstance(raw_cover_page, dict):
        font_size = str(raw_cover_page.get('fontSize') or '12').strip() or '12'
        font_family = str(raw_cover_page.get('fontFamily') or 'Times New Roman').strip() or 'Times New Roman'
        align = str(raw_cover_page.get('align') or 'center').strip().lower() or 'center'
        mode = str(raw_cover_page.get('mode') or 'full').strip().lower() or 'full'
        if mode not in {'full', 'append'}:
            mode = 'full'
        if align not in {'left', 'center', 'right'}:
            align = 'center'
        
        # Build HTML from blocks if blocks exist
        blocks = raw_cover_page.get('blocks')
        if isinstance(blocks, list) and len(blocks) > 0:
            html_value = _build_cover_page_html_from_blocks(blocks, font_size, font_family, align, cover_logos)
        else:
            # Fallback to old html field for backward compatibility
            html_value = str(raw_cover_page.get('html') or '').strip()
        
        return {
            'html': re.sub(r'(?is)<\s*script\b[^>]*>.*?<\s*/\s*script\s*>', '', html_value),
            'fontSize': font_size,
            'fontFamily': font_family,
            'align': align,
            'mode': mode,
        }
    return {
        'html': '',
        'fontSize': '12',
        'fontFamily': 'Times New Roman',
        'align': 'center',
        'mode': 'full',
    }


def _resolve_layout_settings(content, report):
    raw_layout = content.get('__layout', {}) if isinstance(content, dict) else {}

    base = {
        'showHeader': True,
        'showFooter': True,
        'headerLeft': report.user.name if report and report.user else 'Internship Report',
        'headerRight': report.projectTitle if report and report.projectTitle else (report.major.name if report and report.major else 'Project Report'),
        'footerText': 'Prepared as part of internship academic submission',
    }

    if not isinstance(raw_layout, dict):
        return base

    return {
        'showHeader': raw_layout.get('showHeader', True) is not False,
        'showFooter': raw_layout.get('showFooter', True) is not False,
        'headerLeft': str(raw_layout.get('headerLeft') or base['headerLeft']),
        'headerRight': str(raw_layout.get('headerRight') or base['headerRight']),
        'footerText': str(raw_layout.get('footerText') or base['footerText']),
    }


def _is_images_enabled(report):
    if not report or not getattr(report, 'major', None):
        return False

    major = report.major
    policy = getattr(major, 'reportPolicy', None)

    if policy:
        if bool(getattr(policy, 'imagesRequired', False)):
            return True
        features = getattr(policy, 'contentFeatures', []) or []
        if any(str(v).lower() == 'images' for v in features):
            return True

    if bool(getattr(major, 'imagesRequired', False)):
        return True

    section_images = getattr(report, 'sectionImages', None) or {}
    return any(isinstance(v, list) and len(v) > 0 for v in section_images.values())

def _build_pdf_sections(report, content, request_obj=None):
    titles = report.generatedTitles or {}
    resolved = resolve_effective_report_sections(
        major=report.major,
        college=report.college,
        university=report.university,
        include_legacy=True,
    )
    major_sections = resolved['sections'] if report.major else []

    sections = []
    used_keys = set()

    # Keep configured section order first (same idea as old project behavior).
    for section in major_sections:
        key = str(section.get('key', ''))
        if not key:
            continue
        normalized_text = _normalize_section_text((content or {}).get(key, ''))
        if not normalized_text:
            continue
        prepared_text = _repair_markdown_numbering(normalized_text)
        html_content = _md_to_html(prepared_text)
        sections.append({
            'key': key,
            'title': titles.get(key) or section.get('title') or _humanize_key(key),
            'content': html_content,
            'content_before': html_content,
            'content_after': '',
            '_normalized_content': prepared_text,
            'direction': _detect_text_direction(normalized_text),
            'is_rtl': _detect_text_direction(normalized_text) == 'rtl',
        })
        used_keys.add(key)

    # Append any extra generated sections not present in configured list.
    for key, value in (content or {}).items():
        key = str(key)
        if key in used_keys or key.startswith('__'):
            continue
        normalized_text = _normalize_section_text(value)
        if not normalized_text:
            continue
        prepared_text = _repair_markdown_numbering(normalized_text)
        html_content = _md_to_html(prepared_text)
        sections.append({
            'key': key,
            'title': titles.get(key) or _humanize_key(key),
            'content': html_content,
            'content_before': html_content,
            'content_after': '',
            '_normalized_content': prepared_text,
            'direction': _detect_text_direction(normalized_text),
            'is_rtl': _detect_text_direction(normalized_text) == 'rtl',
        })

    section_images = getattr(report, 'sectionImages', None) or {}
    for section in sections:
        key = section['key']
        imgs = section_images.get(key, [])
        if not isinstance(imgs, list):
            imgs = []

        normalized_imgs = []
        for img in imgs:
            if not isinstance(img, dict):
                continue
            item = dict(img)
            if request_obj is not None:
                item['url'] = _normalize_asset_url(item.get('url', ''), request_obj)
            normalized_imgs.append(item)

        for img in normalized_imgs:
            logging.debug(f"[PDF Image URL] {img.get('url')}")

        section['images_top'] = [i for i in normalized_imgs if i.get('position') == 'top']
        section['images_middle'] = [i for i in normalized_imgs if i.get('position') == 'middle']
        section['images_bottom'] = [i for i in normalized_imgs if i.get('position') == 'bottom']

        if section['images_middle']:
            before_text, after_text = _split_content_for_middle_images(section.get('_normalized_content', ''))
            section['content_before'] = _md_to_html(before_text)
            section['content_after'] = _md_to_html(after_text) if after_text else ''

        section.pop('_normalized_content', None)
    return sections


def _serialize_report_list_item(r):
    return {
        '_id': str(r.id),
        'projectTitle': r.projectTitle,
        'status': r.status,
        'academicYear': r.academicYear,
        'createdAt': r.createdAt.isoformat() if r.createdAt else None,
        'degree': {'_id': str(r.degree.id), 'name': r.degree.name} if r.degree else None,
        'major': {'_id': str(r.major.id), 'name': r.major.name, 'reportLanguage': r.major.reportLanguage} if r.major else None,
        'industry': {'_id': str(r.industry.id), 'name': r.industry.name} if r.industry else None,
    }


@reports_bp.route('/my', methods=['GET'])
@token_required
def my_reports(current_user):
    docs = Report.objects(user=current_user.id).order_by('-createdAt')
    return jsonify([_serialize_report_list_item(r) for r in docs])


@reports_bp.route('/<report_id>', methods=['GET'])
@token_required
def get_one_report(current_user, report_id):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    default_cover_logos = _resolve_cover_logos({}, r, request)

    return jsonify({
        '_id': str(r.id),
        'projectTitle': r.projectTitle,
        'internshipTitle': r.internshipTitle,
        'academicYear': r.academicYear,
        'rollNumber': r.rollNumber,
        'studentEmail': r.studentEmail,
        'briefDescription': r.briefDescription,
        'descriptionSource': getattr(r, 'descriptionSource', ''),
        'selectedWorkKeywords': getattr(r, 'selectedWorkKeywords', []) or [],
        'keywordMeta': getattr(r, 'keywordMeta', {}) or {},
        'keySkills': r.keySkills,
        'status': r.status,
        'generatedContent': _sanitize_content_map(r.generatedContent or {}),
        'editedContent': _sanitize_content_map(r.editedContent or {}),
        'defaultCoverLogos': default_cover_logos,
        'generatedTitles': _sanitize_titles_map(r.generatedTitles or {}),
        'sectionImages': r.sectionImages or {},
        'imagesEnabled': _is_images_enabled(r),
        'generatedUiLabels': r.generatedUiLabels,
        'user': {
            '_id': str(r.user.id),
            'name': r.user.name,
            'email': r.user.email,
            'villageCityName': r.user.villageCityName,
            'tehsil': r.user.tehsil,
            'district': r.user.district,
            'state': r.user.state,
            'phone': r.user.phone,
            'rollNumber': r.user.rollNumber,
            'enrollmentNumber': r.user.enrollmentNumber,
        } if r.user else None,
        'degree': {'_id': str(r.degree.id), 'name': r.degree.name} if r.degree else None,
        'major': {
            '_id': str(r.major.id),
            'name': r.major.name,
            'reportLanguage': r.major.reportLanguage,
            'reportContentType': r.major.reportContentType,
            'reportPolicy': r.major.reportPolicy.to_mongo().to_dict() if r.major and r.major.reportPolicy else {},
        } if r.major else None,
        'college': {
            '_id': str(r.college.id),
            'name': r.college.name,
            'villageCityName': r.college.villageCityName,
            'tehsil': r.college.tehsil,
            'district': r.college.district,
            'state': r.college.state,
            'logo': r.college.logo,
            'website': r.college.website,
        } if r.college else None,
        'university': {
            '_id': str(r.university.id),
            'name': r.university.name,
            'villageCityName': r.university.villageCityName,
            'state': r.university.state,
        } if r.university else None,
        'industry': {
            '_id': str(r.industry.id),
            'name': r.industry.name,
            'villageCityName': r.industry.villageCityName,
            'tehsil': r.industry.tehsil,
            'district': r.industry.district,
            'state': r.industry.state,
            'website': r.industry.website,
        } if r.industry else None,
        'createdAt': r.createdAt.isoformat() if r.createdAt else None,
    })


@reports_bp.route('/<report_id>/pdf', methods=['GET'])
@token_required
def download_pdf(current_user, report_id):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    content = r.editedContent or r.generatedContent or {}
    sections = _build_pdf_sections(r, content, request)
    cover_logos = _resolve_cover_logos(content, r, request)
    cover_page_settings = _resolve_cover_page(content, cover_logos)
    layout_settings = _resolve_layout_settings(content, r)

    college = College.objects(id=r.college.id).first() if r.college else None
    university = University.objects(id=r.university.id).first() if r.university else None
    industry = Industry.objects(id=r.industry.id).first() if r.industry else None

    html_string = render_template(
        'pdf_template.html',
        report=r,
        college=college,
        university=university,
        industry=industry,
        cover_logos=cover_logos,
        cover_page_settings=cover_page_settings,
        layout_settings=layout_settings,
        sections=sections,
    )
    base_url = _resolve_public_base_url(request)
    html_string = html_string.replace(
        '<head>',
        f'<head><base href="{base_url}/">',
        1,
    )
    pdf_bytes = generate_pdf_from_html(
        html_string,
        base_url=base_url,
        student_name=r.user.name if r.user else 'Student',
    )

    try:
        r.downloadCount = int(r.downloadCount or 0) + 1
        r.save()
    except Exception:
        pass

    file_name = f"{(r.projectTitle or 'Internship_Report').strip()}.pdf"
    inline_mode = str(request.args.get('inline', '')).strip().lower() in ('1', 'true', 'yes', 'on')
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=not inline_mode,
        download_name=file_name,
    )


@reports_bp.route('/<report_id>/pdf-preview', methods=['POST'])
@token_required
def pdf_preview(current_user, report_id):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    incoming_edited = data.get('editedContent') if isinstance(data.get('editedContent'), dict) else None
    content = incoming_edited or r.editedContent or r.generatedContent or {}
    sections = _build_pdf_sections(r, content, request)
    cover_logos = _resolve_cover_logos(content, r, request)
    cover_page_settings = _resolve_cover_page(content, cover_logos)
    layout_settings = _resolve_layout_settings(content, r)

    college = College.objects(id=r.college.id).first() if r.college else None
    university = University.objects(id=r.university.id).first() if r.university else None
    industry = Industry.objects(id=r.industry.id).first() if r.industry else None

    html_string = render_template(
        'pdf_template.html',
        report=r,
        college=college,
        university=university,
        industry=industry,
        cover_logos=cover_logos,
        cover_page_settings=cover_page_settings,
        layout_settings=layout_settings,
        sections=sections,
    )
    base_url = _resolve_public_base_url(request)
    html_string = html_string.replace(
        '<head>',
        f'<head><base href="{base_url}/">',
        1,
    )
    pdf_bytes = generate_pdf_from_html(
        html_string,
        base_url=base_url,
        student_name=r.user.name if r.user else 'Student',
    )

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name='preview.pdf',
    )


@reports_bp.route('/', methods=['POST'], strict_slashes=False)
@token_required
def create_report(current_user):
    data = request.get_json() or {}
    major_id = str(data.get('major') or '').strip()
    project_title = str(data.get('projectTitle') or '').strip()
    brief_description = str(data.get('briefDescription') or '').strip()
    selected_work_keywords = _normalize_keywords_list(
        data.get('selectedWorkKeywords', data.get('workKeywords', []))
    )
    description_source = str(data.get('descriptionSource') or '').strip().lower()
    keyword_meta = data.get('keywordMeta') if isinstance(data.get('keywordMeta'), dict) else {}

    if not major_id or not project_title:
        return jsonify({'message': 'Missing required fields'}), 400

    description_mode = _get_report_description_mode()
    if description_mode == 'keywords_only':
        if not selected_work_keywords:
            return jsonify({'message': 'Select at least one work keyword to continue'}), 400
        # Enforce keyword-derived summary in strict mode.
        brief_description = ', '.join(selected_work_keywords)
        description_source = 'keywords'
    elif description_mode == 'hybrid':
        if not brief_description and selected_work_keywords:
            brief_description = ', '.join(selected_work_keywords)
        if not brief_description:
            return jsonify({'message': 'Missing required fields'}), 400
        if not description_source:
            description_source = 'keywords' if selected_work_keywords else 'legacy'
    else:
        if not brief_description:
            return jsonify({'message': 'Missing required fields'}), 400
        if not description_source:
            description_source = 'legacy'

    major_doc = Major.objects(id=major_id).first()
    if not major_doc:
        return jsonify({'message': 'Major not found'}), 404

    user = User.objects(id=current_user.id).first() or current_user

    industry_id = data.get('industry') or (str(user.industry.id) if user.industry else None)

    # Determine effective language: allow student override unless policy forbids it
    student_language = str(data.get('reportLanguage') or '').strip()
    policy = getattr(major_doc, 'reportPolicy', None)
    allowed = list(policy.allowedLanguages) if policy and getattr(policy, 'allowedLanguages', None) else []
    strict = bool(getattr(policy, 'strictLanguageOnly', False)) if policy else False

    if student_language:
        if strict:
            effective_language = major_doc.reportLanguage
        elif allowed and student_language not in allowed:
            return jsonify({'message': f'Language "{student_language}" is not allowed for this major. Allowed: {", ".join(allowed)}'}), 400
        else:
            effective_language = student_language
    else:
        effective_language = major_doc.reportLanguage

    report = Report(
        user=user.id,
        degree=major_doc.degree.id if major_doc.degree else None,
        major=major_doc.id,
        college=user.college.id if user.college else None,
        university=user.university.id if user.university else None,
        industry=industry_id,
        rollNumber=data.get('rollNumber', user.rollNumber),
        studentEmail=user.email,
        reportLanguage=major_doc.reportLanguage,
        projectTitle=project_title,
        internshipTitle=data.get('internshipTitle', ''),
        academicYear=data.get('academicYear', ''),
        duration=data.get('duration', ''),
        startDate=data.get('startDate', ''),
        endDate=data.get('endDate', ''),
        positionTitle=data.get('positionTitle', ''),
        supervisorName=data.get('supervisorName', user.supervisorName),
        supervisorContact=data.get('supervisorContact', user.supervisorContact),
        briefDescription=brief_description,
        keySkills=data.get('keySkills', ''),
        status='generating',
    )
    report.descriptionSource = description_source
    report.selectedWorkKeywords = selected_work_keywords
    report.keywordMeta = {
        'jobProfile': str(data.get('jobProfile') or keyword_meta.get('jobProfile') or '').strip(),
        'industryType': str(
            data.get('industryType')
            or keyword_meta.get('industryType')
            or (
                getattr(user, 'industryType', '') if bool(getattr(user, 'industryProfileCustomized', False))
                else (getattr(user.industry, 'industryType', '') if getattr(user, 'industry', None) else '')
            )
            or ''
        ).strip(),
        'mode': description_mode,
    }
    report.save()

    base_backend_url = _resolve_public_base_url(request)
    col_name = user.college.name if user.college else ''
    uni_name = user.university.name if user.university else ''
    ind_doc = Industry.objects(id=industry_id).first() if industry_id else None
    ind_name = ind_doc.name if ind_doc else data.get('industryName', '')
    user_industry_customized = bool(getattr(user, 'industryProfileCustomized', False))
    industry_profile = {
        'name': ind_name,
        'villageCityName': (
            getattr(user, 'industryVillageCityName', '') if user_industry_customized
            else (getattr(ind_doc, 'villageCityName', '') if ind_doc else '')
        ),
        'district': (
            getattr(user, 'industryDistrict', '') if user_industry_customized
            else (getattr(ind_doc, 'district', '') if ind_doc else '')
        ),
        'state': (
            getattr(user, 'industryState', '') if user_industry_customized
            else (getattr(ind_doc, 'state', '') if ind_doc else '')
        ),
        'website': (
            getattr(user, 'industryWebsite', '') if user_industry_customized
            else (getattr(ind_doc, 'website', '') if ind_doc else '')
        ),
        'gstNumber': (
            getattr(user, 'industryGstNumber', '') if user_industry_customized
            else (getattr(ind_doc, 'gstNumber', '') if ind_doc else '')
        ),
        'industryDetails': (
            getattr(user, 'industryDetails', '') if user_industry_customized
            else (getattr(ind_doc, 'industryDetails', '') if ind_doc else '')
        ),
        'industryType': (
            getattr(user, 'industryType', '') if user_industry_customized
            else (getattr(ind_doc, 'industryType', '') if ind_doc else '')
        ),
        'industrySubType': (
            getattr(user, 'industrySubType', '') if user_industry_customized
            else (getattr(ind_doc, 'industrySubType', '') if ind_doc else '')
        ),
        'keyActivities': (
            list(getattr(user, 'industryKeyActivities', []) or []) if user_industry_customized
            else list(getattr(ind_doc, 'keyActivities', []) or [])
        ),
    }

    payload = {
        'reportId': str(report.id),
        'callbackUrl': f"{base_backend_url}/api/reports/{report.id}/generated",
        'student': {
            'name': user.name,
            'email': user.email,
            'rollNumber': report.rollNumber,
            'enrollmentNumber': user.enrollmentNumber,
            'villageCityName': user.villageCityName,
            'district': user.district,
            'state': user.state,
            'gender': getattr(user, 'gender', ''),
            'semester': getattr(user, 'semester', ''),
        },
        'college': {
            'name': col_name,
            'villageCityName': user.college.villageCityName if user.college else '',
            'district': user.college.district if user.college else '',
            'state': user.college.state if user.college else '',
            'website': user.college.website if user.college else '',
        },
        'university': {
            'name': uni_name,
            'villageCityName': user.university.villageCityName if user.university else '',
            'district': user.university.district if user.university else '',
            'state': user.university.state if user.university else '',
        },
        'industry': {
            'name': industry_profile.get('name', ''),
            'villageCityName': industry_profile.get('villageCityName', ''),
            'district': industry_profile.get('district', ''),
            'state': industry_profile.get('state', ''),
            'website': industry_profile.get('website', ''),
            'gstNumber': industry_profile.get('gstNumber', ''),
            'industryDetails': industry_profile.get('industryDetails', ''),
            'industryType': industry_profile.get('industryType', ''),
            'industrySubType': industry_profile.get('industrySubType', ''),
            'keyActivities': industry_profile.get('keyActivities', []),
            'supervisorName': report.supervisorName,
        },
        'academic': {
            'degree': major_doc.degree.name if major_doc.degree else '',
            'department': getattr(getattr(user, 'academicDepartment', None), 'name', '') if getattr(user, 'academicDepartment', None) else '',
            'major': major_doc.name,
            'university': uni_name,
            'college': col_name,
            'collegeCity': user.college.villageCityName if user.college else '',
            'collegeState': user.college.state if user.college else '',
        },
        'internship': {
            'industryName': industry_profile.get('name', ''),
            'industryCity': industry_profile.get('villageCityName', ''),
            'industryState': industry_profile.get('state', ''),
            'industryWebsite': industry_profile.get('website', ''),
            'industryGstNumber': industry_profile.get('gstNumber', ''),
            'industryDetails': industry_profile.get('industryDetails', ''),
            'industryType': industry_profile.get('industryType', ''),
            'industrySubType': industry_profile.get('industrySubType', ''),
            'industryKeyActivities': industry_profile.get('keyActivities', []),
            'supervisorName': report.supervisorName,
            'supervisorContact': report.supervisorContact,
            'projectTitle': report.projectTitle,
            'internshipTitle': report.internshipTitle,
            'academicYear': report.academicYear,
            'duration': report.duration,
            'startDate': report.startDate,
            'endDate': report.endDate,
            'positionTitle': report.positionTitle,
            'briefDescription': report.briefDescription,
            'keySkills': report.keySkills,
            'workKeywords': selected_work_keywords,
            'jobProfile': report.keywordMeta.get('jobProfile', '') if isinstance(getattr(report, 'keywordMeta', {}), dict) else '',
            'descriptionSource': description_source,
        },
        'reportConfig': {
            'language': report.reportLanguage,
            'contentType': major_doc.reportContentType,
            'policy': major_doc.reportPolicy.to_mongo().to_dict() if major_doc.reportPolicy else {},
            'aiContext': major_doc.aiPromptContext,
            'sections': resolve_effective_report_sections(
                major=major_doc,
                college=user.college,
                university=user.university,
                include_legacy=True,
            )['sections'],
        },
    }

    n8n_url = os.getenv('N8N_WEBHOOK_URL')
    callback_secret = os.getenv('N8N_CALLBACK_SECRET', '')
    if n8n_url:
        try:
            # Increased timeout to 120 seconds to allow longer workflows
            # If timeout occurs, leave report in 'generating' state - webhook callback will update it
            headers = {'Content-Type': 'application/json'}
            if callback_secret:
                headers['X-Callback-Secret'] = callback_secret
            n8n_response = requests.post(n8n_url, json=payload, headers=headers, timeout=120)
            if not n8n_response.ok:
                report.status = 'error'
                report.errorMessage = f'Generation service returned error: {n8n_response.status_code}'
                report.save()
        except requests.exceptions.Timeout:
            # Timeout doesn't mean failure - n8n is still running
            # Leave report in 'generating' status and let the webhook callback handle completion
            pass
        except Exception as e:
            report.status = 'error'
            report.errorMessage = f'Generation service error: {str(e)}'
            report.save()

    return jsonify({'message': 'Generating...', 'reportId': str(report.id)}), 201


@reports_bp.route('/<report_id>/generated', methods=['PUT'])
def n8n_generated(report_id):
    callback_secret = os.getenv('N8N_CALLBACK_SECRET', '')
    if callback_secret:
        provided = request.headers.get('X-Callback-Secret', '')
        if not secrets.compare_digest(provided, callback_secret):
            return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json() or {}
    raw_generated_content = data.get('generatedContent', {})
    raw_generated_titles = data.get('generatedTitles', {})
    raw_generated_ui_labels = data.get('generatedUiLabels', {})

    has_object_string_payload = any(
        isinstance(v, str) and '[object Object]' in v
        for v in [raw_generated_content, raw_generated_titles, raw_generated_ui_labels]
    )
    if has_object_string_payload:
        return jsonify({
            'message': (
                'Invalid callback payload from n8n: object fields were sent as strings. '
                'In HTTP Request node JSON body, remove quotes around expressions '
                'or send one full expression object.'
            )
        }), 400

    generated_content = _to_object_if_json(raw_generated_content)
    generated_titles = _to_object_if_json(raw_generated_titles)
    generated_ui_labels = _to_object_if_json(raw_generated_ui_labels)

    if not isinstance(generated_content, dict):
        return jsonify({'message': 'generatedContent must be an object'}), 400

    normalized_content = {}
    normalized_titles = dict(generated_titles) if isinstance(generated_titles, dict) else {}

    for key, value in generated_content.items():
        if isinstance(value, dict):
            normalized_content[key] = _normalize_section_text(value.get('sectionContent', value.get('content', '')))
            title = str(value.get('sectionTitle', value.get('title', ''))).strip()
            if title and key not in normalized_titles:
                normalized_titles[key] = title
        else:
            normalized_content[key] = _normalize_section_text(value)

    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Report not found'}), 404

    r.generatedContent = _sanitize_content_map(normalized_content)
    r.generatedTitles = _sanitize_titles_map(normalized_titles)
    if isinstance(generated_ui_labels, dict):
        r.generatedUiLabels = generated_ui_labels
    r.editedContent = _sanitize_content_map(normalized_content)
    r.status = 'generated'
    r.save()
    return jsonify({'message': 'Saved', 'reportId': str(r.id)}), 200


@reports_bp.route('/<report_id>/content', methods=['PUT'])
@token_required
def update_content(current_user, report_id):
    data = request.get_json() or {}
    if 'editedContent' not in data:
        return jsonify({'message': 'No content provided'}), 400

    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    if str(r.user.id) != str(current_user.id):
        return jsonify({'message': 'Forbidden'}), 403

    r.editedContent = _sanitize_content_map(data['editedContent'])
    r.status = 'edited'
    r.save()
    return jsonify({'message': 'Saved successfully'})


@reports_bp.route('/<report_id>/images/<section_key>', methods=['POST'])
@token_required
def upload_section_image(current_user, report_id, section_key):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    file = request.files.get('image')
    if not file or not file.filename:
        return jsonify({'message': 'No file provided'}), 400

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return jsonify({'message': 'Invalid file type. Allowed: jpg, jpeg, png, gif, webp'}), 400

    # Check file size (max 5MB)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        return jsonify({'message': 'File too large. Maximum size is 5MB.'}), 400

    folder = os.path.join(REPORT_IMAGE_UPLOAD_FOLDER, str(report_id), section_key)
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(folder, filename)
    file.save(filepath)

    url = f"/static/uploads/report_images/{report_id}/{section_key}/{filename}"
    image_entry = {
        'url': url,
        'filename': filename,
        'position': 'bottom',
        'caption': '',
        'widthPercent': 100
    }

    images = dict(r.sectionImages or {})
    section_list = list(images.get(section_key, []))
    section_list.append(image_entry)
    images[section_key] = section_list
    r.sectionImages = images
    r.save()

    return jsonify({'image': image_entry}), 201


@reports_bp.route('/<report_id>/images/<section_key>/<filename>', methods=['PUT'])
@token_required
def update_section_image(current_user, report_id, section_key, filename):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    images = dict(r.sectionImages or {})
    section_list = list(images.get(section_key, []))

    updated = False
    for img in section_list:
        if isinstance(img, dict) and img.get('filename') == filename:
            if 'position' in data:
                img['position'] = str(data['position'])
            if 'caption' in data:
                img['caption'] = str(data['caption'])
            if 'widthPercent' in data:
                try:
                    img['widthPercent'] = max(10, min(100, int(data['widthPercent'])))
                except (ValueError, TypeError):
                    pass
            updated = True
            break

    if not updated:
        return jsonify({'message': 'Image not found'}), 404

    images[section_key] = section_list
    r.sectionImages = images
    r.save()
    return jsonify({'message': 'Updated'})


@reports_bp.route('/<report_id>/images/<section_key>/<filename>', methods=['DELETE'])
@token_required
def delete_section_image(current_user, report_id, section_key, filename):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    images = dict(r.sectionImages or {})
    before = list(images.get(section_key, []))
    after = [i for i in before if not (isinstance(i, dict) and i.get('filename') == filename)]

    if len(before) == len(after):
        return jsonify({'message': 'Image not found'}), 404

    images[section_key] = after
    r.sectionImages = images
    r.save()

    _delete_upload_file(f'/uploads/report_images/{report_id}/{section_key}/{filename}')

    return jsonify({'message': 'Deleted'})


@reports_bp.route('/<report_id>', methods=['DELETE'])
@token_required
def delete_report(current_user, report_id):
    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    if str(r.user.id) != str(current_user.id) and current_user.role != 'admin':
        return jsonify({'message': 'Forbidden'}), 403

    Report.objects(id=report_id).delete()
    shutil.rmtree(os.path.join(REPORT_IMAGE_UPLOAD_FOLDER, str(report_id)), ignore_errors=True)
    return jsonify({'message': 'Deleted'})

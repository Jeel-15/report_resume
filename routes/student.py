import os
import re
import json
import html
import uuid
import datetime
import requests
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from routes.auth import token_required
from models.user import User
from models.degree import Degree
from models.major import Major
from models.report import Report
from models.industry import Industry
from models.service import Service
from models.project_title import ProjectTitle
from models.video_guide import VideoGuide
from models.department import Department
from models.work_keyword import WorkKeyword
from routes.reports import (
    _is_images_enabled,
    _build_pdf_sections,
    _resolve_cover_logos,
    _resolve_layout_settings,
)
# Resume builder models
from models.resume import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeVolunteering,
    ResumeCertification,
    ResumeLanguage,
)
from models.career_objective import CareerObjective
from models.resume_keyword import ResumeKeyword
# We'll need to fetch colleges/universities too
from models.college import College
from models.university import University
from models import AssignmentSession, AssignmentPrompt

student_bp = Blueprint('student', __name__)
REPORT_IMAGE_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'report_images')


def _is_profile_complete(user):
    return bool(
        getattr(user, 'name', None) and
        getattr(user, 'college', None) and
        getattr(user, 'university', None) and
        getattr(user, 'degree', None) and
        getattr(user, 'major', None) and
        getattr(user, 'industry', None)
    )


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
    text = '' if value is None else str(value)
    # Handle literal \n escape sequences (not real newlines) from JSON/webhook payloads
    text = text.replace('\\n', '\n')
    # Handle HTML-encoded br/p tags that bypass regex matching
    text = re.sub(r'&lt;br\s*/?&gt;', '\n', text)
    text = re.sub(r'&lt;/?p\s*&gt;', '\n\n', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded

    text = re.sub(r'(?i)<\s*br\s*/?\s*>', '\n', text)
    text = re.sub(r'(?i)<\s*/\s*p\s*>', '\n\n', text)
    text = re.sub(r'(?i)<\s*p\b[^>]*>', '', text)
    text = re.sub(r'(?i)<\s*/?\s*div\b[^>]*>', '\n', text)
    text = re.sub(r'(?i)<\s*/?\s*li\b[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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


def _serialize_degree(degree):
    return {
        '_id': str(degree.id),
        'name': degree.name,
        'isActive': degree.isActive
    }


def _serialize_major(major):
    return {
        '_id': str(major.id),
        'name': major.name,
        'degree': str(major.degree.id) if major.degree else None,
        'department': {
            '_id': _doc_id(getattr(major, 'department', None)),
            'name': getattr(getattr(major, 'department', None), 'name', ''),
            'degree': _doc_id(getattr(getattr(major, 'department', None), 'degree', None)),
        } if getattr(major, 'department', None) else None,
        'reportLanguage': major.reportLanguage,
        'reportContentType': major.reportContentType,
        'reportPolicy': major.reportPolicy.to_mongo().to_dict() if major.reportPolicy else {},
        'isActive': major.isActive
    }


def _serialize_department(department):
    return {
        '_id': _doc_id(department),
        'name': getattr(department, 'name', ''),
        'degree': _doc_id(getattr(department, 'degree', None)),
        'approvalStatus': _normalized_approval_status(department),
        'rejectionReason': getattr(department, 'rejectionReason', ''),
        'isActive': bool(getattr(department, 'isActive', True)),
    }


def _serialize_work_keyword(doc):
    major_obj = getattr(doc, 'major', None)
    return {
        '_id': _doc_id(doc),
        'keyword': getattr(doc, 'keyword', ''),
        'industryType': getattr(doc, 'industryType', ''),
        'jobProfile': getattr(doc, 'jobProfile', ''),
        'major': {
            '_id': _doc_id(major_obj),
            'name': getattr(major_obj, 'name', ''),
        } if major_obj else None,
        'sortOrder': int(getattr(doc, 'sortOrder', 0) or 0),
        'isActive': bool(getattr(doc, 'isActive', True)),
    }


def _serialize_resume_summary(doc):
    return {
        '_id': _doc_id(doc),
        'title': getattr(doc, 'title', ''),
        'createdAt': getattr(doc, 'createdAt', None).isoformat() if getattr(doc, 'createdAt', None) else None,
        'updatedAt': getattr(doc, 'updatedAt', None).isoformat() if getattr(doc, 'updatedAt', None) else None,
        'user': _doc_id(getattr(doc, 'user', None)),
    }


def _serialize_resume_full(doc):
    # Full serializer: include all top-level fields and serialize embedded lists
    def _serialize_embedded_list(items, mapper):
        return [mapper(i) for i in (items or [])]

    def _edu(e):
        return {
            'degreeName': getattr(e, 'degreeName', ''),
            'collegeUniversityName': getattr(e, 'collegeUniversityName', ''),
            'passingYear': getattr(e, 'passingYear', ''),
            'percentageCgpa': getattr(e, 'percentageCgpa', ''),
            'location': getattr(e, 'location', ''),
            'sortOrder': int(getattr(e, 'sortOrder', 0) or 0)
        }

    def _exp(x):
        return {
            'companyName': getattr(x, 'companyName', ''),
            'position': getattr(x, 'position', ''),
            'duration': getattr(x, 'duration', ''),
            'location': getattr(x, 'location', ''),
            'responsibilities': getattr(x, 'responsibilities', '') or '',
            'rawDutyKeywords': list(getattr(x, 'rawDutyKeywords', []) or []),
            'enhancedDuties': getattr(x, 'enhancedDuties', ''),
            'sortOrder': int(getattr(x, 'sortOrder', 0) or 0)
        }

    def _proj(p):
        return {
            'title': getattr(p, 'title', ''),
            'year': getattr(p, 'year', ''),
            'projectUrl': getattr(p, 'projectUrl', ''),
            'githubUrl': getattr(p, 'githubUrl', ''),
            'description': getattr(p, 'description', '') or '',
            'rawKeywords': list(getattr(p, 'rawKeywords', []) or []),
            'enhancedDescription': getattr(p, 'enhancedDescription', ''),
            'sortOrder': int(getattr(p, 'sortOrder', 0) or 0)
        }

    def _vol(v):
        return {
            'organizationName': getattr(v, 'organizationName', ''),
            'role': getattr(v, 'role', ''),
            'duration': getattr(v, 'duration', ''),
            'description': getattr(v, 'description', '') or '',
            'rawContributionKeywords': list(getattr(v, 'rawContributionKeywords', []) or []),
            'enhancedContributions': getattr(v, 'enhancedContributions', ''),
            'sortOrder': int(getattr(v, 'sortOrder', 0) or 0)
        }

    def _cert(c):
        return {
            'certificationName': getattr(c, 'certificationName', ''),
            'issuingAuthority': getattr(c, 'issuingAuthority', ''),
            'year': getattr(c, 'year', ''),
            'sortOrder': int(getattr(c, 'sortOrder', 0) or 0)
        }

    def _lang(l):
        return {
            'languageName': getattr(l, 'languageName', ''),
            'proficiency': getattr(l, 'proficiency', ''),
            'sortOrder': int(getattr(l, 'sortOrder', 0) or 0)
        }

    return {
        '_id': _doc_id(doc),
        'title': getattr(doc, 'title', ''),
        'fullName': getattr(doc, 'fullName', ''),
        'address': getattr(doc, 'address', ''),
        'phone': getattr(doc, 'phone', ''),
        'email': getattr(doc, 'email', ''),
        'photoUrl': getattr(doc, 'photoUrl', ''),
        'linkedinUrl': getattr(doc, 'linkedinUrl', ''),
        'githubUrl': getattr(doc, 'githubUrl', ''),
        'careerObjectiveRaw': getattr(doc, 'careerObjectiveRaw', ''),
        'careerObjectiveEnhanced': getattr(doc, 'careerObjectiveEnhanced', ''),
        'education': _serialize_embedded_list(getattr(doc, 'education', []), _edu),
        'experience': _serialize_embedded_list(getattr(doc, 'experience', []), _exp),
        'projects': _serialize_embedded_list(getattr(doc, 'projects', []), _proj),
        'volunteering': _serialize_embedded_list(getattr(doc, 'volunteering', []), _vol),
        'certifications': _serialize_embedded_list(getattr(doc, 'certifications', []), _cert),
        'languages': _serialize_embedded_list(getattr(doc, 'languages', []), _lang),
        'skills': list(getattr(doc, 'skills', []) or []),
        'technicalSkills': list(getattr(doc, 'technicalSkills', []) or []),
        'coursework': list(getattr(doc, 'coursework', []) or []),
        'personalSkills': list(getattr(doc, 'personalSkills', []) or []),
        'status': getattr(doc, 'status', ''),
        'errorMessage': getattr(doc, 'errorMessage', ''),
        'createdAt': getattr(doc, 'createdAt', None).isoformat() if getattr(doc, 'createdAt', None) else None,
        'updatedAt': getattr(doc, 'updatedAt', None).isoformat() if getattr(doc, 'updatedAt', None) else None,
        'user': _doc_id(getattr(doc, 'user', None)),
    }


def _serialize_career_objective(doc):
    return {
        '_id': _doc_id(doc),
        'text': getattr(doc, 'text', ''),
        'major': _doc_id(getattr(doc, 'major', None)),
        'approvalStatus': _normalized_approval_status(doc),
        'createdBy': _doc_id(getattr(doc, 'createdBy', None)),
    }


def _serialize_resume_keyword(doc):
    return {
        '_id': _doc_id(doc),
        'keyword': getattr(doc, 'keyword', ''),
        'category': getattr(doc, 'category', ''),
        'industryType': getattr(doc, 'industryType', ''),
        'major': _doc_id(getattr(doc, 'major', None)),
        'isActive': bool(getattr(doc, 'isActive', True)),
    }


def _serialize_university(university):
    return {
        '_id': str(university.id),
        'name': university.name,
        'villageCityName': university.villageCityName,
        'tehsil': university.tehsil,
        'district': university.district,
        'state': university.state,
        'website': university.website,
        'approvalStatus': _normalized_approval_status(university),
        'rejectionReason': getattr(university, 'rejectionReason', ''),
        'isActive': university.isActive
    }


def _serialize_college(college):
    return {
        '_id': str(college.id),
        'name': college.name,
        'university': str(college.university.id) if college.university else None,
        'villageCityName': college.villageCityName,
        'tehsil': college.tehsil,
        'district': college.district,
        'state': college.state,
        'logo': college.logo,
        'website': college.website,
        'approvalStatus': _normalized_approval_status(college),
        'rejectionReason': getattr(college, 'rejectionReason', ''),
        'isActive': college.isActive
    }


def _serialize_industry(industry):
    return {
        '_id': str(industry.id),
        'name': industry.name,
        'villageCityName': industry.villageCityName,
        'tehsil': getattr(industry, 'tehsil', ''),
        'district': getattr(industry, 'district', ''),
        'state': industry.state,
        'website': industry.website,
        'isActive': industry.isActive,
        'approvalStatus': _normalized_approval_status(industry),
        'gstNumber': getattr(industry, 'gstNumber', ''),
        'industryDetails': getattr(industry, 'industryDetails', ''),
        'industryType': getattr(industry, 'industryType', ''),
        'industrySubType': getattr(industry, 'industrySubType', ''),
        'keyActivities': list(getattr(industry, 'keyActivities', []) or []),
    }


def _serialize_user_industry_profile(user):
    industry = getattr(user, 'industry', None)
    customized = bool(getattr(user, 'industryProfileCustomized', False))
    profile = {
        'name': getattr(industry, 'name', ''),
        'villageCityName': getattr(industry, 'villageCityName', ''),
        'tehsil': getattr(industry, 'tehsil', ''),
        'district': getattr(industry, 'district', ''),
        'state': getattr(industry, 'state', ''),
        'website': getattr(industry, 'website', ''),
        'gstNumber': getattr(industry, 'gstNumber', ''),
        'industryDetails': getattr(industry, 'industryDetails', ''),
        'industryType': getattr(industry, 'industryType', ''),
        'industrySubType': getattr(industry, 'industrySubType', ''),
        'keyActivities': list(getattr(industry, 'keyActivities', []) or []),
        'customized': customized,
    }

    if customized:
        profile.update({
            'villageCityName': getattr(user, 'industryVillageCityName', ''),
            'tehsil': getattr(user, 'industryTehsil', ''),
            'district': getattr(user, 'industryDistrict', ''),
            'state': getattr(user, 'industryState', ''),
            'website': getattr(user, 'industryWebsite', ''),
            'gstNumber': getattr(user, 'industryGstNumber', ''),
            'industryDetails': getattr(user, 'industryDetails', ''),
            'industryType': getattr(user, 'industryType', ''),
            'industrySubType': getattr(user, 'industrySubType', ''),
            'keyActivities': list(getattr(user, 'industryKeyActivities', []) or []),
        })

    return profile


def _serialize_profile(user):
    university_logo_override = str(getattr(user, 'universityLogoOverride', '') or '').strip()
    college_logo_override = str(getattr(user, 'collegeLogoOverride', '') or '').strip()
    university_logo_master = str(getattr(getattr(user, 'university', None), 'logo', '') or '').strip()
    college_logo_master = str(getattr(getattr(user, 'college', None), 'logo', '') or '').strip()
    university_effective_logo = university_logo_override or university_logo_master
    college_effective_logo = college_logo_override or college_logo_master

    return {
        '_id': str(user.id),
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'profileCompleted': user.profileCompleted,
        'villageCityName': user.villageCityName,
        'tehsil': user.tehsil,
        'district': user.district,
        'state': user.state,
        'phone': user.phone,
        'whatsapp': user.whatsapp,
        'gender': getattr(user, 'gender', ''),
        'semester': getattr(user, 'semester', ''),
        'department': getattr(user, 'department', ''),
        'academicDepartment': _serialize_department(user.academicDepartment) if getattr(user, 'academicDepartment', None) else None,
        'rollNumber': user.rollNumber,
        'enrollmentNumber': user.enrollmentNumber,
        'supervisorName': user.supervisorName,
        'supervisorContact': user.supervisorContact,
        'university': _serialize_university(user.university) if user.university else None,
        'college': _serialize_college(user.college) if user.college else None,
        'universityLogoOverride': university_logo_override,
        'collegeLogoOverride': college_logo_override,
        'universityEffectiveLogo': university_effective_logo,
        'collegeEffectiveLogo': college_effective_logo,
        'degree': _serialize_degree(user.degree) if user.degree else None,
        'major': _serialize_major(user.major) if user.major else None,
        'industry': _serialize_industry(user.industry) if user.industry else None,
        'industryProfile': _serialize_user_industry_profile(user),
    }


def _serialize_service(service):
    return {
        '_id': str(service.id),
        'name': service.name,
        'type': service.type,
        'price': service.price,
        'gstIncluded': service.gstIncluded,
        'gstPercent': service.gstPercent,
        'freeLimit': service.freeLimit,
        'description': service.description,
        'isActive': service.isActive,
        'degreePricing': [
            {
                'degree': {
                    '_id': str(item.degree.id),
                    'name': item.degree.name,
                } if item.degree else None,
                'price': item.price,
            } for item in (service.degreePricing or [])
        ],
    }


def _doc_id(value):
    if value is None:
        return ''
    # Try .id attribute first (MongoEngine document)
    direct = getattr(value, 'id', None)
    if direct is not None:
        return str(direct).strip()
    # Try ._id attribute
    nested = getattr(value, '_id', None)
    if nested is not None:
        return str(nested).strip()
    # Try ._data dict (SQLite backend stores raw values here)
    raw_data = getattr(value, '_data', None)
    if isinstance(raw_data, dict):
        raw_id = raw_data.get('id') or raw_data.get('_id')
        if raw_id is not None:
            return str(raw_id).strip()
    # Fallback: stringify the value itself
    result = str(value).strip()
    # Strip quotes if SQLite stored it as "'abc123'" (quoted string)
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    return result


def _ids_match(id_a, id_b):
    """
    Safely compare two IDs that may come from SQLite (int or string)
    or MongoEngine documents. Normalizes both to plain strings.
    """
    if id_a is None and id_b is None:
        return True
    if id_a is None or id_b is None:
        return False
    return str(id_a).strip() == str(id_b).strip()


def _is_creator(doc, current_user):
    creator = (
        getattr(doc, 'user', None)
        or getattr(doc, 'createdBy', None)
        or getattr(doc, 'creator', None)
    )
    return _ids_match(_doc_id(creator), _doc_id(current_user))


def _normalized_approval_status(doc):
    # Backward compatibility: older records may have null/empty approvalStatus.
    status = str(getattr(doc, 'approvalStatus', '') or '').strip().lower()
    return status if status in {'approved', 'pending', 'rejected'} else 'approved'


def _is_visible_to_student(doc, current_user):
    return _normalized_approval_status(doc) == 'approved' or _is_creator(doc, current_user)


def _is_active_record(doc):
    return bool(getattr(doc, 'isActive', True))


def _filter_major_docs(docs, degree_id='', department_doc=None):
    import sys
    degree_id = str(degree_id or '').strip()
    print(f"[DEBUG _filter_major_docs] ENTRY: degree_id={degree_id!r}, department_doc={department_doc}, total docs={len(docs)}", file=sys.stderr)
    
    # Resolve degree document for internal ID comparison
    degree_doc = None
    degree_internal_id = None
    if degree_id:
        print(f"[DEBUG] Looking up Degree with id={degree_id!r}...", file=sys.stderr)
        degree_doc = Degree.objects(id=degree_id).first()
        if degree_doc:
            degree_internal_id = getattr(degree_doc, 'id', None)
            print(f"[DEBUG] Degree found: {degree_doc.name!r}, internal_id={degree_internal_id!r}", file=sys.stderr)
        else:
            print(f"[DEBUG] Degree NOT found! degree_id={degree_id!r}", file=sys.stderr)

    department_id = _doc_id(department_doc) if department_doc else ''
    department_internal_id = getattr(department_doc, 'id', None) if department_doc else None
    department_degree_id = _doc_id(
        getattr(department_doc, 'degree', None)
    ) if department_doc else ''

    def _degree_matches(doc_degree_field):
        """Check if a major's degree field matches the target degree."""
        if not degree_id:
            return True
        if doc_degree_field is None:
            return False
        if degree_doc is None:
            return False
        # Strategy 1: Direct document comparison
        try:
            if doc_degree_field == degree_doc:
                return True
        except Exception:
            pass
        # Strategy 2: Internal ID comparison
        try:
            field_id = getattr(doc_degree_field, 'id', None)
            if (field_id is not None and degree_internal_id is not None and
                    str(field_id) == str(degree_internal_id)):
                return True
        except Exception:
            pass
        # Strategy 3: _doc_id string comparison
        try:
            if _ids_match(_doc_id(doc_degree_field), _doc_id(degree_doc)):
                return True
        except Exception:
            pass
        return False

    def _department_matches(doc_dept_field):
        """Check if a major's department field matches the target department."""
        if not department_doc:
            return True
        if doc_dept_field is None:
            return False
        # Strategy 1: Direct comparison
        try:
            if doc_dept_field == department_doc:
                return True
        except Exception:
            pass
        # Strategy 2: Internal ID comparison
        try:
            field_id = getattr(doc_dept_field, 'id', None)
            if (field_id is not None and department_internal_id is not None and
                    str(field_id) == str(department_internal_id)):
                return True
        except Exception:
            pass
        # Strategy 3: _doc_id string comparison
        try:
            if _ids_match(_doc_id(doc_dept_field), department_id):
                return True
        except Exception:
            pass
        return False

    filtered = []
    for i, doc in enumerate(docs):
        major_degree_field = getattr(doc, 'degree', None)
        major_dept_field = getattr(doc, 'department', None)
        major_dept_id = _doc_id(major_dept_field)
        
        if i < 5:  # Log first 5 majors for debugging
            print(f"[DEBUG] Major #{i}: name={doc.name!r}, degree={major_degree_field!r}, dept={major_dept_field!r}", file=sys.stderr)

        if department_doc:
            # Filtering by department
            if _department_matches(major_dept_field):
                filtered.append(doc)
                print(f"[DEBUG] ✓ Major {doc.name!r} matched department", file=sys.stderr)
                continue
            # Backward compat: legacy majors (no dept) under same degree
            if (not major_dept_id and major_degree_field and
                    _degree_matches(major_degree_field)):
                filtered.append(doc)
                print(f"[DEBUG] ✓ Major {doc.name!r} matched legacy (no dept, same degree)", file=sys.stderr)
            continue

        # Filtering by degree only
        if degree_id and not _degree_matches(major_degree_field):
            if i < 5:
                print(f"[DEBUG] ✗ Major {doc.name!r} did NOT match degree", file=sys.stderr)
            continue
        
        if i < 5:
            print(f"[DEBUG] ✓ Major {doc.name!r} matched", file=sys.stderr)
        filtered.append(doc)

    print(f"[DEBUG _filter_major_docs] EXIT: filtered {len(filtered)} from {len(docs)}", file=sys.stderr)
    return filtered


def _parse_pagination(default_limit=None, max_limit=200):
    """Parse limit/offset from query params with clamped bounds."""
    limit_raw = str(request.args.get('limit', '')).strip()
    offset_raw = str(request.args.get('offset', '')).strip()

    try:
        offset = max(int(offset_raw or 0), 0)
    except (TypeError, ValueError):
        offset = 0

    if limit_raw:
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = default_limit if default_limit is not None else max_limit
        limit = min(max(limit, 1), max_limit)
        return limit, offset

    if default_limit is not None:
        return min(max(int(default_limit), 1), max_limit), offset

    return None, offset


def _slice_items(items, limit=None, offset=0):
    if limit is None:
        return items[offset:] if offset else items
    return items[offset: offset + limit]


@student_bp.route('/degrees', methods=['GET'])
@token_required
def get_degrees(current_user):
    degrees = [degree for degree in Degree.objects().order_by('name') if _is_active_record(degree)]
    limit, offset = _parse_pagination(default_limit=None, max_limit=300)
    degrees = _slice_items(degrees, limit=limit, offset=offset)
    return jsonify([_serialize_degree(degree) for degree in degrees])


@student_bp.route('/degrees', methods=['POST'])
@token_required
def create_degree(current_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'Degree name is required'}), 400

    existing = next(
        (doc for doc in Degree.objects() if str(getattr(doc, 'name', '')).strip().lower() == name.lower()),
        None,
    )
    if existing:
        return jsonify(_serialize_degree(existing)), 200

    degree = Degree(
        name=name,
        isActive=True,
        createdBy=current_user,
        approvalStatus='pending',
    )
    degree.save()
    return jsonify(_serialize_degree(degree)), 201


@student_bp.route('/majors', methods=['GET'])
@token_required
def get_all_active_majors(current_user):
    degree_id = str(request.args.get('degree', '')).strip()
    department_id = str(request.args.get('department', '')).strip()

    majors = [major for major in Major.objects().order_by('name') if _is_active_record(major)]
    department_doc = None
    if department_id:
        department_doc = Department.objects(id=department_id).first()
        if not department_doc:
            return jsonify({'message': 'Invalid department'}), 400

    majors = _filter_major_docs(majors, degree_id=degree_id, department_doc=department_doc)
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)
    majors = _slice_items(majors, limit=limit, offset=offset)
    return jsonify([_serialize_major(major) for major in majors])


@student_bp.route('/majors/<degree_id>', methods=['GET'])
@token_required
def get_majors_by_degree(current_user, degree_id):
    import sys
    print(f"[DEBUG get_majors_by_degree] degree_id={degree_id!r}", file=sys.stderr)
    
    department_id = str(request.args.get('department', '')).strip()
    majors = [major for major in Major.objects().order_by('name') if _is_active_record(major)]
    print(f"[DEBUG get_majors_by_degree] Total active majors in DB: {len(majors)}", file=sys.stderr)
    
    department_doc = None
    if department_id:
        print(f"[DEBUG get_majors_by_degree] Looking up Department with id={department_id!r}...", file=sys.stderr)
        department_doc = Department.objects(id=department_id).first()
        if not department_doc:
            print(f"[DEBUG get_majors_by_degree] Department NOT found!", file=sys.stderr)
            return jsonify({'message': 'Invalid department'}), 400
        print(f"[DEBUG get_majors_by_degree] Department found: {department_doc.name!r}", file=sys.stderr)

    majors = _filter_major_docs(majors, degree_id=degree_id, department_doc=department_doc)
    print(f"[DEBUG get_majors_by_degree] After filtering: {len(majors)} majors", file=sys.stderr)
    
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)
    majors = _slice_items(majors, limit=limit, offset=offset)
    return jsonify([_serialize_major(major) for major in majors])


@student_bp.route('/majors', methods=['POST'])
@token_required
def create_major(current_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    degree_id = str(data.get('degree', '')).strip()
    department_id = str(data.get('department', '')).strip()

    if not name or not degree_id:
        return jsonify({'message': 'Major name and degree are required'}), 400

    degree_doc = Degree.objects(id=degree_id).first()
    if not degree_doc:
        return jsonify({'message': 'Invalid degree'}), 400

    department_doc = None
    if department_id:
        department_doc = Department.objects(id=department_id).first()
        if not department_doc:
            return jsonify({'message': 'Invalid department'}), 400
        if _doc_id(getattr(department_doc, 'degree', None)) != _doc_id(degree_doc):
            return jsonify({'message': 'Selected department does not belong to selected degree'}), 400

    existing = next(
        (
            doc for doc in Major.objects()
            if str(getattr(doc, 'name', '')).strip().lower() == name.lower()
            and _doc_id(getattr(doc, 'degree', None)) == _doc_id(degree_doc)
            and _doc_id(getattr(doc, 'department', None)) == _doc_id(department_doc)
        ),
        None,
    )
    if existing:
        return jsonify(_serialize_major(existing)), 200

    major = Major(
        name=name,
        degree=degree_doc,
        department=department_doc,
        isActive=True,
        createdBy=current_user,
        approvalStatus='pending',
    )
    major.save()
    return jsonify(_serialize_major(major)), 201


@student_bp.route('/departments', methods=['GET'])
@token_required
def get_departments(current_user):
    import sys
    degree_id = str(request.args.get('degree', '')).strip()
    query = str(request.args.get('q', '')).strip().lower()

    limit, offset = _parse_pagination(default_limit=100, max_limit=300)

    # Resolve the degree document first so we can compare 
    # by the actual SQLite internal ID
    degree_doc = None
    degree_internal_id = None
    if degree_id:
        print(f"[DEBUG] Looking up Degree with id={degree_id!r}...", file=sys.stderr)
        degree_doc = Degree.objects(id=degree_id).first()
        print(f"[DEBUG] Degree lookup result: {degree_doc}", file=sys.stderr)
        if degree_doc:
            degree_internal_id = getattr(degree_doc, 'id', None)
            print(f"[DEBUG] Degree found! name={degree_doc.name!r}, id={degree_internal_id!r}", file=sys.stderr)
        else:
            print(f"[DEBUG] Degree NOT found! This will cause all departments to be skipped.", file=sys.stderr)

    print(f"[DEBUG get_departments] degree_id={degree_id!r} "
          f"degree_doc={degree_doc} "
          f"degree_internal_id={degree_internal_id!r}", 
          file=sys.stderr)

    visible = []
    for department in Department.objects().order_by('name'):
        if not _is_active_record(department):
            continue

        # Filter by degree using resolved document comparison
        if degree_id:
            if not degree_doc:
                # degree_id given but not found in DB — return empty
                print(f"[DEBUG] Skipping all departments because degree_doc lookup failed", file=sys.stderr)
                continue
            dept_degree = getattr(department, 'degree', None)
            if dept_degree is None:
                continue
            
            if degree_id and degree_doc:
                raw_data = getattr(department, '_data', {}) or {}
                print(f"[DEBUG dept] name={department.name!r} "
                      f"dept_degree={dept_degree!r} "
                      f"dept_degree.id={getattr(dept_degree, 'id', None)!r} "
                      f"raw_data.degree={raw_data.get('degree')!r}",
                      file=sys.stderr)
            
            # Compare using multiple strategies to handle SQLite 
            # integer FK vs string ID inconsistency
            dept_degree_matches = False
            match_strategy = None
            
            # Strategy 1: Direct document comparison
            try:
                if dept_degree == degree_doc:
                    dept_degree_matches = True
                    match_strategy = "Strategy 1 (direct comparison)"
                    print(f"[DEBUG] ✓ {match_strategy}", file=sys.stderr)
            except Exception as e:
                print(f"[DEBUG] Strategy 1 error: {e}", file=sys.stderr)
            
            # Strategy 2: Compare internal IDs (SQLite integer FK)
            if not dept_degree_matches:
                try:
                    dept_degree_id_val = getattr(dept_degree, 'id', None)
                    print(f"[DEBUG] Strategy 2: comparing {dept_degree_id_val!r} == {degree_internal_id!r}", file=sys.stderr)
                    if (dept_degree_id_val is not None and 
                            degree_internal_id is not None and
                            str(dept_degree_id_val) == str(degree_internal_id)):
                        dept_degree_matches = True
                        match_strategy = "Strategy 2 (internal IDs)"
                        print(f"[DEBUG] ✓ {match_strategy}", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Strategy 2 error: {e}", file=sys.stderr)
            
            # Strategy 3: _ids_match on _doc_id strings
            if not dept_degree_matches:
                try:
                    did = _doc_id(dept_degree)
                    gdid = _doc_id(degree_doc)
                    print(f"[DEBUG] Strategy 3: comparing _doc_id({did!r}) == _doc_id({gdid!r})", file=sys.stderr)
                    if _ids_match(did, gdid):
                        dept_degree_matches = True
                        match_strategy = "Strategy 3 (_doc_id strings)"
                        print(f"[DEBUG] ✓ {match_strategy}", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Strategy 3 error: {e}", file=sys.stderr)
            
            # Strategy 4: Compare string representations of 
            # the degree field directly from _data dict
            if not dept_degree_matches:
                try:
                    raw_data = getattr(department, '_data', {}) or {}
                    raw_degree_val = raw_data.get('degree')
                    deg_internal_str = str(degree_internal_id).strip() if degree_internal_id else ''
                    deg_external_str = str(degree_id).strip()
                    print(f"[DEBUG] Strategy 4: raw_degree_val={raw_degree_val!r}, comparing with internal={deg_internal_str!r} or external={deg_external_str!r}", file=sys.stderr)
                    if raw_degree_val is not None:
                        raw_deg_str = str(raw_degree_val).strip()
                        if raw_deg_str and (raw_deg_str == deg_internal_str or raw_deg_str == deg_external_str):
                            dept_degree_matches = True
                            match_strategy = "Strategy 4 (raw _data)"
                            print(f"[DEBUG] ✓ {match_strategy}", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Strategy 4 error: {e}", file=sys.stderr)

            if not dept_degree_matches:
                print(f"[DEBUG] ✗ Department {department.name!r} did NOT match any strategy", file=sys.stderr)
                continue
            else:
                print(f"[DEBUG] ✓ Department {department.name!r} matched via {match_strategy}", file=sys.stderr)

        # Filter by approvalStatus
        status = _normalized_approval_status(department)
        if status not in ('approved', 'pending'):
            continue
        if status == 'pending':
            creator_id = _doc_id(getattr(department, 'createdBy', None))
            if creator_id and not _ids_match(creator_id, _doc_id(current_user)):
                continue

        # Filter by search query
        if query and query not in str(getattr(department, 'name', '')).lower():
            continue

        visible.append(department)
        if len(visible) >= (offset + limit if limit is not None else 1000):
            break

    visible = _slice_items(visible, limit=limit, offset=offset)
    print(f"[DEBUG get_departments] FINAL: returning {len(visible)} departments", file=sys.stderr)
    return jsonify([_serialize_department(department) for department in visible])


@student_bp.route('/departments', methods=['POST'])
@token_required
def create_department(current_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    degree_id = str(data.get('degree', '')).strip()

    if not name or not degree_id:
        return jsonify({'message': 'Department name and degree are required'}), 400

    degree_doc = Degree.objects(id=degree_id).first()
    if not degree_doc:
        return jsonify({'message': 'Invalid degree'}), 400

    existing = next(
        (
            doc for doc in Department.objects()
            if str(getattr(doc, 'name', '')).strip().lower() == name.lower()
            and _doc_id(getattr(doc, 'degree', None)) == _doc_id(degree_doc)
        ),
        None,
    )
    if existing:
        return jsonify(_serialize_department(existing)), 200

    department = Department(
        name=name,
        degree=degree_doc,
        createdBy=current_user,
        approvalStatus='pending',
        isActive=True,
    )
    department.save()
    return jsonify(_serialize_department(department)), 201


@student_bp.route('/major/<major_id>', methods=['GET'])
@token_required
def get_major(current_user, major_id):
    major = Major.objects(id=major_id).first()
    if not major:
        return jsonify({'message': 'Major not found'}), 404
    return jsonify(_serialize_major(major))


@student_bp.route('/universities', methods=['GET'])
@token_required
def get_universities(current_user):
    query = str(request.args.get('q', '')).strip()
    q_lower = query.lower()
    limit, offset = _parse_pagination(default_limit=50, max_limit=200)
    visible = []
    # NOTE: mongoengine's isActive=True query filter doesn't work with SQLite backend.
    # Fetch all and filter in Python instead.
    for university in University.objects().order_by('name'):
        if not getattr(university, 'isActive', True):
            continue
        if query and q_lower not in str(university.name or '').lower():
            continue
        if not _is_visible_to_student(university, current_user):
            continue
        visible.append(university)
        if len(visible) >= (offset + limit if limit is not None else 500):
            break

    visible = _slice_items(visible, limit=limit, offset=offset)
    return jsonify([_serialize_university(university) for university in visible])


@student_bp.route('/universities', methods=['POST'])
@token_required
def create_university(current_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'University name is required'}), 400

    existing = next((u for u in University.objects() if str(u.name or '').strip().lower() == name.lower()), None)
    if existing:
        return jsonify(_serialize_university(existing)), 200

    university = University(
        name=name,
        createdBy=current_user,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        logo=str(data.get('logo', '')).strip(),
        approvalStatus='pending',
        isVerified=False,
    )
    university.save()
    return jsonify(_serialize_university(university)), 201


@student_bp.route('/colleges', methods=['GET'])
@token_required
def get_colleges(current_user):
    query = str(request.args.get('q', '')).strip()
    university_id = str(request.args.get('university', '')).strip()

    q_lower = query.lower()
    limit, offset = _parse_pagination(default_limit=50, max_limit=300)
    visible = []
    # NOTE: mongoengine's isActive=True query filter doesn't work with SQLite backend.
    # Fetch all and filter in Python instead.
    for college in College.objects().order_by('name'):
        if not getattr(college, 'isActive', True):
            continue
        if query and q_lower not in str(college.name or '').lower():
            continue
        if university_id and _doc_id(getattr(college, 'university', None)) != university_id:
            continue
        if not _is_visible_to_student(college, current_user):
            continue
        visible.append(college)
        if len(visible) >= (offset + limit if limit is not None else 500):
            break

    visible = _slice_items(visible, limit=limit, offset=offset)
    return jsonify([_serialize_college(college) for college in visible])


@student_bp.route('/colleges', methods=['POST'])
@token_required
def create_college(current_user):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    university_id = str(data.get('university', '')).strip()

    if not name or not university_id:
        return jsonify({'message': 'College name and university are required'}), 400

    university_doc = University.objects(id=university_id).first()
    if not university_doc:
        return jsonify({'message': 'Invalid university'}), 400

    existing = next(
        (
            c for c in College.objects()
            if str(c.name or '').strip().lower() == name.lower()
            and _doc_id(getattr(c, 'university', None)) == _doc_id(university_doc)
        ),
        None,
    )
    if existing:
        return jsonify(_serialize_college(existing)), 200

    college = College(
        name=name,
        university=university_doc,
        createdBy=current_user,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        logo=str(data.get('logo', '')).strip(),
        approvalStatus='pending',
        isVerified=False,
    )
    college.save()
    return jsonify(_serialize_college(college)), 201


@student_bp.route('/industries', methods=['GET'])
@token_required
def get_industries(current_user):
    query = str(request.args.get('q', '')).strip()
    q_lower = query.lower()
    limit, offset = _parse_pagination(default_limit=50, max_limit=300)
    visible = []
    # mongoengine's BooleanField query filter is unreliable with the SQLite-backed store.
    # Fetch all industries and filter active ones in Python instead.
    for industry in Industry.objects().order_by('name'):
        if not getattr(industry, 'isActive', True):
            continue
        if query and q_lower not in str(industry.name or '').lower():
            continue
        if not _is_visible_to_student(industry, current_user):
            continue
        visible.append(industry)
        if len(visible) >= (offset + limit if limit is not None else 500):
            break

    visible = _slice_items(visible, limit=limit, offset=offset)
    return jsonify([_serialize_industry(industry) for industry in visible])


@student_bp.route('/industries', methods=['POST'])
@token_required
def create_industry(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'Industry name is required'}), 400

    existing = Industry.objects(name__iexact=name).first()
    if existing:
        return jsonify(_serialize_industry(existing)), 200

    key_activities_raw = data.get('keyActivities', [])
    if isinstance(key_activities_raw, list):
        key_activities = [str(item).strip() for item in key_activities_raw if str(item).strip()]
    else:
        key_activities = [
            line.strip() for line in str(key_activities_raw or '').replace('\r\n', '\n').split('\n')
            if line.strip()
        ]

    industry = Industry(
        name=name,
        createdBy=current_user,
        approvalStatus='pending',           # student-created industries need admin approval
        isActive=True,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        gstNumber=str(data.get('gstNumber', '')).strip(),
        industryDetails=str(data.get('industryDetails', '')).strip(),
        industryType=str(data.get('industryType', '')).strip(),
        industrySubType=str(data.get('industrySubType', '')).strip(),
        keyActivities=key_activities,
    )
    industry.save()
    return jsonify(_serialize_industry(industry)), 201


@student_bp.route('/work-keywords-debug', methods=['GET'])
@token_required
def get_work_keywords_debug(current_user):
    """Debug endpoint - returns ALL keywords without filtering"""
    docs = list(WorkKeyword.objects().order_by('sortOrder', 'keyword'))
    return jsonify({
        'total': len(docs),
        'data': [_serialize_work_keyword(doc) for doc in docs]
    })


@student_bp.route('/work-keywords', methods=['GET'])
@token_required
def get_work_keywords(current_user):
    import sys
    industry_type = str(request.args.get('industryType', '')).strip().lower()
    job_profile = str(request.args.get('jobProfile', '')).strip().lower()
    query = str(request.args.get('q', '')).strip().lower()
    major_id = str(request.args.get('major', '')).strip()

    print(f"[DEBUG /work-keywords] Incoming params: industry_type='{industry_type}', job_profile='{job_profile}', query='{query}', major_id='{major_id}'", file=sys.stderr)

    all_keywords = [doc for doc in WorkKeyword.objects().order_by('sortOrder', 'keyword') if _is_active_record(doc)]
    print(f"[DEBUG /work-keywords] Total active keywords: {len(all_keywords)}", file=sys.stderr)
    
    docs = all_keywords
    if industry_type:
        docs = [doc for doc in docs if industry_type in str(getattr(doc, 'industryType', '')).lower()]
    if job_profile:
        docs = [doc for doc in docs if job_profile in str(getattr(doc, 'jobProfile', '')).lower()]
    if query:
        docs = [doc for doc in docs if query in str(getattr(doc, 'keyword', '')).lower()]
    
    print(f"[DEBUG /work-keywords] After industry/job/query filters: {len(docs)} keywords", file=sys.stderr)
    
    # Major filter: show universal keywords (major=None) OR keywords matching the given major
    if major_id:
        universal_keywords = [doc for doc in docs if not getattr(doc, 'major', None)]
        print(f"[DEBUG /work-keywords] Universal keywords (no major): {len(universal_keywords)}", file=sys.stderr)
        
        major_specific = []
        for doc in docs:
            raw_major = getattr(doc, 'major', None)
            if raw_major:
                extracted_id = _doc_id(raw_major)
                match = _ids_match(extracted_id, major_id)
                if match:
                    major_specific.append(doc)
                    print(f"[DEBUG /work-keywords] ✓ Keyword '{doc.keyword}' matches major. extracted_id='{extracted_id}', major_id='{major_id}'", file=sys.stderr)
        
        print(f"[DEBUG /work-keywords] Major-specific keywords matched: {len(major_specific)}", file=sys.stderr)
        docs = universal_keywords + major_specific

    print(f"[DEBUG /work-keywords] Final result: {len(docs)} keywords", file=sys.stderr)
    
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)
    docs = _slice_items(docs, limit=limit, offset=offset)
    return jsonify([_serialize_work_keyword(doc) for doc in docs])


@student_bp.route('/career-objectives', methods=['GET'])
@token_required
def get_career_objectives(current_user):
    major_id = str(request.args.get('major', '')).strip()
    query = str(request.args.get('q', '')).strip().lower()
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)

    docs = [d for d in CareerObjective.objects().order_by('-createdAt') if _is_visible_to_student(d, current_user)]
    if major_id:
        filtered = []
        for d in docs:
            m = getattr(d, 'major', None)
            if not m:
                filtered.append(d)
                continue
            if _ids_match(_doc_id(m), major_id):
                filtered.append(d)
        docs = filtered

    if query:
        docs = [d for d in docs if query in str(getattr(d, 'text', '')).lower()]

    docs = _slice_items(docs, limit=limit, offset=offset)
    return jsonify([_serialize_career_objective(d) for d in docs])


@student_bp.route('/career-objectives/submit', methods=['POST'])
@token_required
def submit_career_objective(current_user):
    data = request.get_json() or {}
    text = str(data.get('text', '')).strip()
    major_id = str(data.get('major', '')).strip()
    if not text:
        return jsonify({'message': 'Text is required'}), 400

    major_doc = None
    if major_id:
        major_doc = Major.objects(id=major_id).first()
        if not major_doc:
            return jsonify({'message': 'Invalid major'}), 400

    obj = CareerObjective(
        text=text,
        major=major_doc,
        createdBy=current_user,
        approvalStatus='pending',
        isActive=True,
    )
    obj.save()
    return jsonify(_serialize_career_objective(obj)), 201


@student_bp.route('/resume-keywords', methods=['GET'])
@token_required
def get_resume_keywords(current_user):
    category = str(request.args.get('category', '')).strip().lower()
    if not category:
        return jsonify({'message': 'category is required'}), 400
    major_id = str(request.args.get('major', '')).strip()
    industry_type = str(request.args.get('industryType', '')).strip().lower()
    q = str(request.args.get('q', '')).strip().lower()
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)

    docs = [d for d in ResumeKeyword.objects().order_by('keyword') if _is_active_record(d)]
    docs = [d for d in docs if str(getattr(d, 'category', '')).strip().lower() == category]
    if industry_type:
        docs = [d for d in docs if industry_type in str(getattr(d, 'industryType', '')).lower()]
    if q:
        docs = [d for d in docs if q in str(getattr(d, 'keyword', '')).lower()]
    if major_id:
        universal = [d for d in docs if not getattr(d, 'major', None)]
        major_specific = [d for d in docs if getattr(d, 'major', None) and _ids_match(_doc_id(getattr(d, 'major', None)), major_id)]
        docs = universal + major_specific

    docs = _slice_items(docs, limit=limit, offset=offset)
    return jsonify([_serialize_resume_keyword(d) for d in docs])


@student_bp.route('/resumes', methods=['GET'])
@token_required
def list_resumes(current_user):
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)
    docs = [r for r in Resume.objects().order_by('-updatedAt') if _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user))]
    docs = _slice_items(docs, limit=limit, offset=offset)
    return jsonify([_serialize_resume_summary(r) for r in docs])


@student_bp.route('/resumes', methods=['POST'])
@token_required
def create_resume(current_user):
    data = request.get_json() or {}
    title = str(data.get('title', '')).strip() or 'Untitled'
    resume = Resume(
        title=title,
        user=current_user,
        createdAt=datetime.datetime.utcnow(),
        updatedAt=datetime.datetime.utcnow(),
    )
    resume.save()
    return jsonify(_serialize_resume_full(resume)), 201


@student_bp.route('/resumes/<resume_id>', methods=['GET'])
@token_required
def get_resume(current_user, resume_id):
    r = Resume.objects(id=resume_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if not _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user)):
        return jsonify({'message': 'Forbidden'}), 403
    return jsonify(_serialize_resume_full(r))


@student_bp.route('/resumes/<resume_id>', methods=['PUT'])
@token_required
def update_resume(current_user, resume_id):
    r = Resume.objects(id=resume_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if not _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user)):
        return jsonify({'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    try:
        # Allowed scalar fields
        for field in ['title', 'fullName', 'address', 'phone', 'email', 'photoUrl', 'linkedinUrl', 'githubUrl', 'careerObjectiveRaw', 'careerObjectiveEnhanced', 'status', 'errorMessage']:
            if field in data:
                setattr(r, field, data.get(field))

        # Lists / embedded documents
        if 'education' in data:
            items = data.get('education') or []
            try:
                r.education = [ResumeEducation(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid education data', 'error': str(e)}), 400
        if 'experience' in data:
            items = data.get('experience') or []
            try:
                r.experience = [ResumeExperience(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid experience data', 'error': str(e)}), 400
        if 'projects' in data:
            items = data.get('projects') or []
            try:
                r.projects = [ResumeProject(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid projects data', 'error': str(e)}), 400
        if 'volunteering' in data:
            items = data.get('volunteering') or []
            try:
                r.volunteering = [ResumeVolunteering(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid volunteering data', 'error': str(e)}), 400
        if 'certifications' in data:
            items = data.get('certifications') or []
            try:
                r.certifications = [ResumeCertification(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid certifications data', 'error': str(e)}), 400
        if 'languages' in data:
            items = data.get('languages') or []
            try:
                r.languages = [ResumeLanguage(**item) for item in items]
            except Exception as e:
                return jsonify({'message': 'Invalid languages data', 'error': str(e)}), 400
        if 'skills' in data:
            r.skills = list(data.get('skills') or [])
        if 'technicalSkills' in data:
            r.technicalSkills = list(data.get('technicalSkills') or [])
        if 'coursework' in data:
            r.coursework = list(data.get('coursework') or [])
        if 'personalSkills' in data:
            r.personalSkills = list(data.get('personalSkills') or [])

        r.updatedAt = datetime.datetime.utcnow()
        r.save()
        return jsonify(_serialize_resume_full(r))
    except Exception as e:
        return jsonify({'message': 'Failed to update resume', 'error': str(e)}), 500


@student_bp.route('/resumes/<resume_id>', methods=['DELETE'])
@token_required
def delete_resume(current_user, resume_id):
    r = Resume.objects(id=resume_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if not _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user)):
        return jsonify({'message': 'Forbidden'}), 403
    try:
        r.delete()
    except Exception:
        pass
    return jsonify({'message': 'Deleted'}), 200


@student_bp.route('/resumes/<resume_id>/pdf', methods=['GET', 'POST'])
@token_required
def resume_pdf(current_user, resume_id):
    """
    GET: Download final resume PDF (from saved DB data)
    POST: Preview resume PDF with edited form data (live preview)
    """
    from flask import render_template, request as flask_request, send_file
    import io
    import markdown as _markdown
    try:
        import bleach as _bleach
        _HAS_BLEACH = True
    except Exception:
        _bleach = None
        _HAS_BLEACH = False
    from utils.pdf import generate_pdf_from_html

    r = Resume.objects(id=resume_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if not _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user)):
        return jsonify({'message': 'Forbidden'}), 403

    # For POST (preview): use form data sent by client
    # For GET (download): use saved data from DB
    if flask_request.method == 'POST':
        data = flask_request.get_json(silent=True) or {}
        resume_data = data.get('resumeData', {})
        as_attachment = False
        file_name = 'preview.pdf'
    else:
        resume_data = _serialize_resume_full(r)
        preview_mode = str(flask_request.args.get('preview', '')).lower() in {'1', 'true', 'yes'}
        as_attachment = not preview_mode
        file_name = f"resume_{_doc_id(r)}.pdf" if not preview_mode else 'preview.pdf'

    # Convert selected resume fields from Markdown to sanitized HTML so
    # bold/italic and lists render correctly in the generated PDF.
    def md_to_safe_html(text):
        if not text:
            return ''
        # Convert basic markdown to HTML
        raw = _markdown.markdown(text, extensions=['extra', 'sane_lists'])
        # If bleach is available, use it for robust sanitization
        if _HAS_BLEACH and _bleach is not None:
            allowed_tags_base = _bleach.sanitizer.ALLOWED_TAGS
            if isinstance(allowed_tags_base, frozenset):
                allowed_tags = allowed_tags_base | {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i'}
            else:
                allowed_tags = set(allowed_tags_base) | {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i'}
            allowed_attrs = {'a': ['href', 'title', 'rel', 'target']}
            clean = _bleach.clean(raw, tags=allowed_tags, attributes=allowed_attrs, strip=True)
            return clean

        # Fallback sanitizer (best-effort) when bleach isn't installed
        import re
        # remove script/style blocks
        raw = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', raw)
        # allowlist of tags
        allowed = {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'a'}

        # remove attributes from allowed tags except for anchor href/title
        def _filter_tag(m):
            tag = m.group(1).lower()
            attrs = m.group(2) or ''
            if tag in allowed:
                if tag == 'a':
                    href = re.search(r'href\s*=\s*"([^"]*)"', attrs)
                    title = re.search(r'title\s*=\s*"([^"]*)"', attrs)
                    out = '<a'
                    if href:
                        out += f' href="{href.group(1)}"'
                    if title:
                        out += f' title="{title.group(1)}"'
                    out += '>'
                    return out
                return f'<{tag}>'
            return ''

        # strip disallowed opening tags (but keep allowed tags with minimal attrs)
        cleaned = re.sub(r'<\s*([a-zA-Z0-9]+)([^>]*)>', _filter_tag, raw)
        # strip closing tags that are not allowed
        cleaned = re.sub(r'</\s*([a-zA-Z0-9]+)\s*>', lambda m: f'</{m.group(1)}>' if m.group(1).lower() in allowed else '', cleaned)
        return cleaned

    # Mutate a shallow copy so the original object isn't harmed
    rd = dict(resume_data) if isinstance(resume_data, dict) else resume_data

    # Career objective
    if isinstance(rd.get('careerObjectiveRaw'), str):
        rd['careerObjectiveHtml'] = md_to_safe_html(rd.get('careerObjectiveRaw'))

    # Experience responsibilities
    for exp in rd.get('experience', []) or []:
        if isinstance(exp.get('responsibilities'), str):
            exp['responsibilitiesHtml'] = md_to_safe_html(exp.get('responsibilities'))

    # Projects descriptions
    for proj in rd.get('projects', []) or []:
        if isinstance(proj.get('description'), str):
            proj['descriptionHtml'] = md_to_safe_html(proj.get('description'))

    # Volunteering descriptions
    for vol in rd.get('volunteering', []) or []:
        if isinstance(vol.get('description'), str):
            vol['descriptionHtml'] = md_to_safe_html(vol.get('description'))

    html_string = render_template(
        'resume_pdf_template.html',
        resume=rd,
        profile=_serialize_profile(current_user),
        user=_serialize_profile(current_user)
    )
    base_url = flask_request.host_url.rstrip('/')
    if '<head>' in html_string:
        html_string = html_string.replace('<head>', f'<head><base href="{base_url}/">', 1)

    pdf_bytes = generate_pdf_from_html(html_string, base_url=base_url, student_name=current_user.name if getattr(current_user, 'name', None) else 'Student')
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=as_attachment,
        download_name=file_name,
    )


@student_bp.route('/resumes/<resume_id>/html-preview', methods=['POST'])
@token_required
def resume_html_preview(current_user, resume_id):
    """
    Fast HTML preview endpoint for the resume builder live preview panel.
    Returns rendered `resume_pdf_template.html` as plain HTML (no Playwright).
    """
    from flask import render_template as _render, make_response, request as flask_request
    import markdown as _markdown

    try:
        import bleach as _bleach
        _HAS_BLEACH = True
    except Exception:
        _bleach = None
        _HAS_BLEACH = False

    r = Resume.objects(id=resume_id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404
    if not _ids_match(_doc_id(getattr(r, 'user', None)), _doc_id(current_user)):
        return jsonify({'message': 'Forbidden'}), 403

    data = flask_request.get_json(silent=True) or {}
    resume_data = data.get('resumeData', {})
    if not isinstance(resume_data, dict):
        resume_data = {}

    def md_to_safe_html(text):
        if not text:
            return ''
        raw = _markdown.markdown(str(text), extensions=['extra', 'sane_lists'])
        if _HAS_BLEACH and _bleach is not None:
            allowed_tags_base = _bleach.sanitizer.ALLOWED_TAGS
            if isinstance(allowed_tags_base, frozenset):
                allowed_tags = allowed_tags_base | {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i'}
            else:
                allowed_tags = set(allowed_tags_base) | {'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i'}
            allowed_attrs = {'a': ['href', 'title', 'rel', 'target']}
            return _bleach.clean(raw, tags=allowed_tags, attributes=allowed_attrs, strip=True)
        import re
        raw = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', raw)
        return raw

    rd = dict(resume_data)

    if isinstance(rd.get('careerObjectiveRaw'), str):
        rd['careerObjectiveHtml'] = md_to_safe_html(rd.get('careerObjectiveRaw'))

    for exp in rd.get('experience', []) or []:
        if isinstance(exp.get('responsibilities'), str):
            exp['responsibilitiesHtml'] = md_to_safe_html(exp.get('responsibilities'))

    for proj in rd.get('projects', []) or []:
        if isinstance(proj.get('description'), str):
            proj['descriptionHtml'] = md_to_safe_html(proj.get('description'))

    for vol in rd.get('volunteering', []) or []:
        if isinstance(vol.get('description'), str):
            vol['descriptionHtml'] = md_to_safe_html(vol.get('description'))

    html_string = _render(
        'resume_pdf_template.html',
        resume=rd,
        profile=_serialize_profile(current_user),
        user=_serialize_profile(current_user)
    )

    base_url = flask_request.host_url.rstrip('/')
    if '<head>' in html_string:
        html_string = html_string.replace(
            '<head>',
            f'<head><base href="{base_url}/">'
            '<style>'
            'html,body{margin:0;padding:16px;background:#e2e8f0;}'
            '.page{width:595px;margin:0 auto;background:#fff;box-shadow:0 4px 24px rgba(0,0,0,0.18);border-radius:2px;padding:24px 28px;box-sizing:border-box;}'
            '</style>',
            1
        )

    response = make_response(html_string, 200)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store'
    return response


# ── Assignment Studio Helpers ─────────────────────────────────────────────

def _serialize_assignment_session(s, include_sections=False, include_chat=False):
    out = {
        '_id':              str(getattr(s, 'id', '') or ''),
        'title':            str(getattr(s, 'title', '') or 'Untitled Assignment'),
        'assignmentType':   str(getattr(s, 'assignmentType', '') or ''),
        'universityName':   str(getattr(s, 'universityName', '') or ''),
        'degreeName':       str(getattr(s, 'degreeName', '') or ''),
        'majorName':        str(getattr(s, 'majorName', '') or ''),
        'status':           str(getattr(s, 'status', 'draft') or 'draft'),
        'errorMessage':     str(getattr(s, 'errorMessage', '') or ''),
        'wordCountCurrent': int(getattr(s, 'wordCountCurrent', 0) or 0),
        'wordCountTarget':  int(getattr(s, 'wordCountTarget', 0) or 0),
        'generationCount':  int(getattr(s, 'generationCount', 0) or 0),
        'contextInputs':    dict(getattr(s, 'contextInputs', {}) or {}),
        'createdAt':        s.createdAt.isoformat() if getattr(s, 'createdAt', None) else '',
        'updatedAt':        s.updatedAt.isoformat() if getattr(s, 'updatedAt', None) else '',
    }
    if include_sections:
        out['documentSections'] = list(getattr(s, 'documentSections', []) or [])
        out['fullContentMarkdown'] = str(getattr(s, 'fullContentMarkdown', '') or '')
    if include_chat:
        out['chatHistory'] = list(getattr(s, 'chatHistory', []) or [])
    return out


def _get_user_sessions(current_user):
    all_sessions = list(AssignmentSession.objects())
    user_id = getattr(current_user, 'id', None)
    sessions = [
        s for s in all_sessions
        if not bool(getattr(s, 'isDeleted', False))
        and (
            str(getattr(getattr(s, 'user', None), 'id', None)) == str(user_id)
            or str(getattr(s, '_data', {}).get('user', '')) == str(user_id)
        )
    ]
    sessions.sort(key=lambda s: getattr(s, 'createdAt', datetime.datetime.min), reverse=True)
    return sessions


def _get_applicable_prompts(university_name, assignment_type):
    all_prompts = list(AssignmentPrompt.objects())
    active = [p for p in all_prompts if bool(getattr(p, 'isActive', True))]
    matched = []
    uname_lower = str(university_name or '').lower()
    for p in active:
        atype = str(getattr(p, 'assignmentType', '*') or '*')
        if atype not in ('*', assignment_type):
            continue
        keywords = list(getattr(p, 'triggerKeywords', []) or [])
        if not keywords:
            matched.append(p)
        elif any(kw.lower() in uname_lower for kw in keywords if kw):
            matched.append(p)
    matched.sort(key=lambda p: int(getattr(p, 'sortOrder', 0) or 0))
    return [str(getattr(p, 'injectedInstruction', '') or '') for p in matched]


def _extract_markdown_from_llm_item(item):
    """Extract markdown text from OpenAI/n8n response item shapes."""
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ''

    chunks = []

    direct_md = item.get('content_markdown')
    if isinstance(direct_md, str) and direct_md.strip():
        return direct_md.strip()

    content_parts = item.get('content')
    if isinstance(content_parts, list):
        for part in content_parts:
            if not isinstance(part, dict):
                continue
            text_val = part.get('text')
            if isinstance(text_val, str) and text_val.strip():
                chunks.append(text_val.strip())

    output_items = item.get('output')
    if isinstance(output_items, dict):
        output_items = [output_items]
    if isinstance(output_items, list):
        for out in output_items:
            if not isinstance(out, dict):
                continue
            out_content = out.get('content')
            if isinstance(out_content, list):
                for part in out_content:
                    if not isinstance(part, dict):
                        continue
                    text_val = part.get('text')
                    if isinstance(text_val, str) and text_val.strip():
                        chunks.append(text_val.strip())

    for key in ('markdown', 'content', 'text'):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val.strip())

    return '\n\n'.join([c for c in chunks if c]).strip()


def _normalize_assignment_callback_sections(raw_sections):
    """Normalize mixed n8n payload shapes into assignment section dicts."""
    if not isinstance(raw_sections, list):
        return []

    normalized = []
    used_keys = set()

    for idx, sec in enumerate(raw_sections):
        if not isinstance(sec, dict):
            continue

        markdown = str(_extract_markdown_from_llm_item(sec) or '').strip()

        title = str(sec.get('title') or '').strip()
        if not title and markdown:
            match = re.search(r'^\s*##\s+(.+?)\s*$', markdown, flags=re.MULTILINE)
            if match:
                title = match.group(1).strip()
        if not title:
            title = f'Section {idx + 1}'

        base_key = str(sec.get('section_key') or sec.get('key') or '').strip().lower()
        if not base_key:
            base_key = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_') or f'section_{idx + 1}'

        key = base_key
        suffix = 2
        while key in used_keys:
            key = f'{base_key}_{suffix}'
            suffix += 1
        used_keys.add(key)

        try:
            sort_order = int(sec.get('sort_order', idx + 1) or (idx + 1))
        except Exception:
            sort_order = idx + 1

        normalized.append({
            'section_key': key,
            'title': title,
            'content_markdown': markdown,
            'sort_order': sort_order,
        })

    normalized.sort(key=lambda x: int(x.get('sort_order', 0) or 0))
    return normalized


# ── Assignment Studio Routes ──────────────────────────────────────────────


@student_bp.route('/assignments', methods=['GET'])
@token_required
def get_assignments(current_user):
    try:
        sessions = _get_user_sessions(current_user)

        filter_type = request.args.get('type', '').strip()
        filter_status = request.args.get('status', '').strip()
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        if filter_type:
            sessions = [s for s in sessions if getattr(s, 'assignmentType', '') == filter_type]
        if filter_status:
            sessions = [s for s in sessions if getattr(s, 'status', '') == filter_status]

        total = len(sessions)
        page = sessions[offset: offset + limit]

        return jsonify({
            'items': [_serialize_assignment_session(s) for s in page],
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments', methods=['POST'])
@token_required
def create_assignment(current_user):
    try:
        data = request.get_json(silent=True) or {}
        assignment_type = str(data.get('assignmentType', '') or '').strip()
        valid_types = ('essay', 'research_paper', 'lab_report', 'case_study', 'presentation_script')
        if assignment_type not in valid_types:
            return jsonify({'message': f'Invalid assignmentType. Must be one of: {valid_types}'}), 400

        context = dict(data.get('contextInputs', {}) or {})
        word_target = int(context.get('wordCountTarget', 800) or 800)

        uni_name = str(getattr(current_user, 'universityName', '') or '')
        deg_name = str(getattr(current_user, 'degreeName', '') or '')
        major_name = str(getattr(current_user, 'majorName', '') or '')

        topic = (
            context.get('topic') or
            context.get('experimentTitle') or
            context.get('caseTitle') or
            context.get('researchTopic') or
            context.get('presentationTitle') or
            ''
        )
        title = str(topic).strip()[:120] or 'Untitled Assignment'

        session = AssignmentSession(
            user=current_user,
            title=title,
            assignmentType=assignment_type,
            universityName=uni_name,
            degreeName=deg_name,
            majorName=major_name,
            contextInputs=context,
            wordCountTarget=word_target,
            status='draft',
        )
        session.save()

        return jsonify({
            'success': True,
            'session': _serialize_assignment_session(session),
        }), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>', methods=['GET'])
@token_required
def get_assignment(current_user, session_id):
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        if bool(getattr(s, 'isDeleted', False)):
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403
        return jsonify(_serialize_assignment_session(s, include_sections=True, include_chat=True)), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/clone', methods=['POST'])
@token_required
def clone_assignment(current_user, session_id):
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        # Create a new draft prefilled from the snapshot (no generated content)
        new_title = f"Copy of {str(getattr(s, 'title', '') or 'Untitled Assignment')}"
        session = AssignmentSession(
            user=current_user,
            title=new_title,
            assignmentType=str(getattr(s, 'assignmentType', '') or 'essay'),
            universityName=str(getattr(s, 'universityName', '') or ''),
            degreeName=str(getattr(s, 'degreeName', '') or ''),
            majorName=str(getattr(s, 'majorName', '') or ''),
            contextInputs=dict(getattr(s, 'contextInputs', {}) or {}),
            wordCountTarget=int(getattr(s, 'wordCountTarget', 0) or 0),
            status='draft',
        )
        session.save()

        return jsonify({'success': True, 'session': _serialize_assignment_session(session)}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>', methods=['PUT'])
@token_required
def update_assignment(current_user, session_id):
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        if str(getattr(s, 'status', '') or '') == 'generated':
            return jsonify({'message': 'Generated assignments are locked. Create a new draft to edit.'}), 409

        data = request.get_json(silent=True) or {}

        if 'title' in data:
            s.title = str(data['title'] or '').strip()[:120] or 'Untitled Assignment'
        if 'assignmentType' in data:
            next_type = str(data['assignmentType'] or '').strip()
            valid_types = ('essay', 'research_paper', 'lab_report', 'case_study', 'presentation_script')
            if next_type and next_type in valid_types and next_type != str(getattr(s, 'assignmentType', '') or ''):
                s.assignmentType = next_type
        if 'contextInputs' in data:
            s.contextInputs = dict(data['contextInputs'] or {})
            word_target = int(s.contextInputs.get('wordCountTarget', s.wordCountTarget) or s.wordCountTarget)
            s.wordCountTarget = word_target

        s.updatedAt = datetime.datetime.utcnow()
        s.save()

        return jsonify({
            'success': True,
            'updatedAt': s.updatedAt.isoformat(),
            'title': str(s.title or ''),
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>', methods=['DELETE'])
@token_required
def delete_assignment(current_user, session_id):
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403
        s.isDeleted = True
        s.updatedAt = datetime.datetime.utcnow()
        s.save()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/generate', methods=['POST'])
@token_required
def generate_assignment(current_user, session_id):
    import os
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        s.status = 'generating'
        s.errorMessage = ''
        s.generationCount = int(getattr(s, 'generationCount', 0) or 0) + 1
        s.updatedAt = datetime.datetime.utcnow()
        s.save()

        n8n_url = os.getenv('N8N_ASSIGNMENT_WEBHOOK_URL', '').strip()
        backend_url = os.getenv('BACKEND_URL', '').strip()
        callback_url = f'{backend_url}/api/student/assignments/{session_id}/callback'

        uni_name = str(getattr(s, 'universityName', '') or '')
        atype = str(getattr(s, 'assignmentType', '') or '')
        injections = _get_applicable_prompts(uni_name, atype)

        payload = {
            'sessionId': str(s.id),
            'assignmentType': atype,
            'contextInputs': dict(getattr(s, 'contextInputs', {}) or {}),
            'universityName': uni_name,
            'degreeName': str(getattr(s, 'degreeName', '') or ''),
            'majorName': str(getattr(s, 'majorName', '') or ''),
            'promptInjections': injections,
            'callbackUrl': callback_url,
        }

        if n8n_url:
            try:
                response = requests.post(n8n_url, json=payload, timeout=(3, 8))
                if response.status_code >= 400:
                    s.status = 'error'
                    s.errorMessage = f'n8n returned {response.status_code}'
                    s.save()
                    return jsonify({'message': 'Generation service returned an error'}), 502
            except requests.exceptions.ReadTimeout:
                # n8n webhook can be configured to respond only after long-running generation.
                # Treat read timeout as accepted and rely on callback + polling for completion.
                pass
            except Exception as n8n_err:
                s.status = 'error'
                s.errorMessage = f'n8n unreachable: {str(n8n_err)[:200]}'
                s.save()
                return jsonify({'message': 'Generation service unavailable', 'error': str(n8n_err)}), 502
        else:
            s.status = 'error'
            s.errorMessage = 'N8N_ASSIGNMENT_WEBHOOK_URL not configured'
            s.save()
            return jsonify({'message': 'N8N_ASSIGNMENT_WEBHOOK_URL not set in .env'}), 500

        return jsonify({'success': True, 'status': 'generating', 'message': 'Generation started. Poll /status for progress.'}), 202
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/callback', methods=['POST'])
def assignment_generation_callback(session_id):
    try:
        data = request.get_json(silent=True) or {}

        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Session not found'}), 404

        raw_sections = data.get('document_sections', []) or []
        sections = _normalize_assignment_callback_sections(raw_sections)

        full_markdown = str(data.get('full_content_markdown', '') or '')
        word_count = int(data.get('word_count', 0) or 0)
        tokens_used = int(data.get('api_tokens_consumed', 0) or 0)

        full_without_separators = re.sub(r'\s*---\s*', '', full_markdown or '').strip()
        if not full_without_separators:
            full_markdown = '\n\n---\n\n'.join([
                str(sec.get('content_markdown', '') or '').strip()
                for sec in sections
                if str(sec.get('content_markdown', '') or '').strip()
            ]).strip()

        if not word_count and full_markdown:
            word_count = len([w for w in full_markdown.split() if w])

        s.documentSections = sections
        s.fullContentMarkdown = full_markdown
        s.wordCountCurrent = word_count
        s.apiTokensConsumed = int(getattr(s, 'apiTokensConsumed', 0) or 0) + tokens_used
        s.status = 'generated'
        s.errorMessage = ''
        s.updatedAt = datetime.datetime.utcnow()
        s.save()

        return jsonify({'success': True}), 200
    except Exception as e:
        try:
            s = AssignmentSession.objects(id=session_id).first()
            if s:
                s.status = 'error'
                s.errorMessage = str(e)[:500]
                s.save()
        except Exception:
            pass
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/status', methods=['GET'])
@token_required
def assignment_status(current_user, session_id):
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403
        return jsonify({
            'status': str(getattr(s, 'status', 'draft') or 'draft'),
            'wordCountCurrent': int(getattr(s, 'wordCountCurrent', 0) or 0),
            'errorMessage': str(getattr(s, 'errorMessage', '') or ''),
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/chat', methods=['POST'])
@token_required
def assignment_chat(current_user, session_id):
    import os
    from openai import OpenAI
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        data = request.get_json(silent=True) or {}
        user_message = str(data.get('message', '') or '').strip()
        if not user_message:
            return jsonify({'message': 'message is required'}), 400

        current_markdown = str(getattr(s, 'fullContentMarkdown', '') or '')
        if not current_markdown:
            return jsonify({'message': 'No generated content to refine. Generate first.'}), 400

        ctx = dict(getattr(s, 'contextInputs', {}) or {})

        system_prompt = f"""You are a document refinement engine for academic assignments.
You receive a complete academic document and a student instruction.
Revise the ENTIRE document according to the instruction while preserving:
- All ## section headings (exactly as they appear)
- Overall document structure
- Academic quality and voice

Document: {str(getattr(s, 'title', '') or '')}
Type: {str(getattr(s, 'assignmentType', '') or '')}
Current words: {int(getattr(s, 'wordCountCurrent', 0) or 0)}
Target words: {int(getattr(s, 'wordCountTarget', 0) or 0)}
Citation style: {ctx.get('citationStyle', 'None')}

RULES:
1. Apply the instruction to the full document, not just one section.
2. Preserve all ## section headings exactly as written.
3. Maintain total word count within ±15% of current count.
4. Output ONLY the complete revised document in Markdown. Nothing else.
5. No preamble like "Here is the revised document:" — start directly with content."""

        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))
        model = os.getenv('OPENAI_MODEL', 'gpt-4.1')

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'CURRENT DOCUMENT:\n"""\n{current_markdown}\n"""\n\nINSTRUCTION: {user_message}'},
            ],
            temperature=0.5,
            max_tokens=4000,
        )

        revised_markdown = response.choices[0].message.content.strip()
        new_word_count = len([w for w in revised_markdown.split() if w])

        import re
        section_parts = re.split(r'\n(?=## )', revised_markdown)
        new_sections = []
        existing_sections = list(getattr(s, 'documentSections', []) or [])

        for i, part in enumerate(section_parts):
            part = part.strip()
            if not part:
                continue
            heading_match = re.match(r'^## (.+)', part)
            title = heading_match.group(1).strip() if heading_match else f'Section {i+1}'
            existing = next((sec for sec in existing_sections if sec.get('title', '').strip().lower() == title.lower()), None)
            section_key = existing.get('section_key', f'sec_{i+1}') if existing else f'sec_{i+1}'
            new_sections.append({
                'section_key': section_key,
                'title': title,
                'content_markdown': part,
                'sort_order': i + 1,
            })

        chat_history = list(getattr(s, 'chatHistory', []) or [])
        chat_history.append({'role': 'user', 'message': user_message, 'timestamp': datetime.datetime.utcnow().isoformat()})
        assistant_summary = f'Revised document. New word count: {new_word_count}.'
        chat_history.append({'role': 'assistant', 'message': assistant_summary, 'timestamp': datetime.datetime.utcnow().isoformat()})

        s.documentSections = new_sections
        s.fullContentMarkdown = revised_markdown
        s.wordCountCurrent = new_word_count
        s.chatHistory = chat_history[-20:]
        s.updatedAt = datetime.datetime.utcnow()
        s.save()

        return jsonify({'success': True, 'documentSections': new_sections, 'wordCountCurrent': new_word_count, 'assistantMessage': assistant_summary}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/sections/<section_key>/rewrite', methods=['POST'])
@token_required
def rewrite_section(current_user, session_id, section_key):
    import os
    from openai import OpenAI
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        data = request.get_json(silent=True) or {}
        instruction = str(data.get('refinementInstruction', '') or '').strip()
        if not instruction:
            return jsonify({'message': 'refinementInstruction is required'}), 400

        sections = list(getattr(s, 'documentSections', []) or [])
        target_section = next((sec for sec in sections if sec.get('section_key') == section_key), None)
        if not target_section:
            return jsonify({'message': f'Section {section_key} not found'}), 404

        ctx = dict(getattr(s, 'contextInputs', {}) or {})
        old_content = str(target_section.get('content_markdown', '') or '')
        old_word_count = len([w for w in old_content.split() if w])

        system_prompt = f"""You are an academic writing refinement engine.
You will rewrite ONE section of an academic document based on a student's instruction.
Preserve: the section heading (## {target_section.get('title', '')})
Preserve: academic quality, formal tone, and citation style ({ctx.get('citationStyle', 'None')})
Output ONLY the revised section in Markdown, starting with ## {target_section.get('title', '')}
No preamble. No explanation."""

        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))
        model = os.getenv('OPENAI_MODEL', 'gpt-4.1')

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'CURRENT SECTION:\n"""\n{old_content}\n"""\n\nINSTRUCTION: {instruction}'},
            ],
            temperature=0.6,
            max_tokens=1200,
        )

        revised_content = response.choices[0].message.content.strip()
        new_word_count = len([w for w in revised_content.split() if w])
        word_count_delta = new_word_count - old_word_count

        updated_sections = []
        for sec in sections:
            if sec.get('section_key') == section_key:
                updated_sections.append({**sec, 'content_markdown': revised_content})
            else:
                updated_sections.append(dict(sec))

        updated_sections_sorted = sorted(updated_sections, key=lambda x: int(x.get('sort_order', 0) or 0))
        full_markdown = '\n\n---\n\n'.join([sec.get('content_markdown', '') for sec in updated_sections_sorted])
        new_total_words = len([w for w in full_markdown.split() if w])

        s.documentSections = updated_sections
        s.fullContentMarkdown = full_markdown
        s.wordCountCurrent = new_total_words
        s.updatedAt = datetime.datetime.utcnow()
        s.save()

        return jsonify({'success': True, 'sectionKey': section_key, 'updatedContentMarkdown': revised_content, 'wordCountDelta': word_count_delta, 'wordCountCurrent': new_total_words}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/pdf', methods=['GET'])
@token_required
def download_assignment_pdf(current_user, session_id):
    import io
    from flask import send_file, render_template
    from utils.pdf import generate_pdf_from_html
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        sections = list(getattr(s, 'documentSections', []) or [])
        if not sections:
            return jsonify({'message': 'Assignment not yet generated'}), 400

        html_content = render_template('assignment_pdf_template.html', session=_serialize_assignment_session(s, include_sections=True), user=_serialize_profile(current_user))
        pdf_bytes = generate_pdf_from_html(html_content)

        safe_title = str(getattr(s, 'title', 'assignment') or 'assignment')
        safe_title = ''.join(c for c in safe_title if c.isalnum() or c in ' _-')[:60].strip().replace(' ', '_')
        filename = f'{safe_title}_assignment.pdf'

        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@student_bp.route('/assignments/<session_id>/docx', methods=['GET'])
@token_required
def download_assignment_docx(current_user, session_id):
    import io
    from flask import send_file
    from utils.docx_generator import generate_docx_from_sections
    try:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            return jsonify({'message': 'Not found'}), 404
        user_id = getattr(current_user, 'id', None)
        session_user_id = getattr(getattr(s, 'user', None), 'id', None) or getattr(s, '_data', {}).get('user', None)
        if str(session_user_id) != str(user_id):
            return jsonify({'message': 'Forbidden'}), 403

        sections = list(getattr(s, 'documentSections', []) or [])
        if not sections:
            return jsonify({'message': 'Assignment not yet generated'}), 400
        metadata = {
            'title': str(getattr(s, 'title', '') or 'Assignment'),
            'assignmentType': str(getattr(s, 'assignmentType', '') or ''),
            'studentName': str(getattr(current_user, 'name', '') or ''),
            'universityName': str(getattr(s, 'universityName', '') or ''),
            'degreeName': str(getattr(s, 'degreeName', '') or ''),
            'wordCount': int(getattr(s, 'wordCountCurrent', 0) or 0),
        }

        doc_io = generate_docx_from_sections(sections, metadata)

        safe_title = str(getattr(s, 'title', 'assignment') or 'assignment')
        safe_title = ''.join(c for c in safe_title if c.isalnum() or c in ' _-')[:60].strip().replace(' ', '_')
        filename = f'{safe_title}_assignment.docx'

        return send_file(doc_io, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'message': str(e)}), 500




@student_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify(_serialize_profile(current_user))


@student_bp.route('/services', methods=['GET'])
@token_required
def get_services(current_user):
    services = [service for service in Service.objects().order_by('name') if _is_active_record(service)]
    limit, offset = _parse_pagination(default_limit=None, max_limit=200)
    services = _slice_items(services, limit=limit, offset=offset)
    return jsonify([_serialize_service(service) for service in services])


@student_bp.route('/profile/personal', methods=['PUT'])
@token_required
def update_personal_profile(current_user):
    data = request.get_json() or {}
    allowed_fields = ['name', 'villageCityName', 'tehsil', 'district', 'state', 'phone', 'whatsapp', 'gender']

    for field in allowed_fields:
        if field in data:
            setattr(current_user, field, data[field])

    current_user.profileCompleted = _is_profile_complete(current_user)
    current_user.updatedAt = datetime.datetime.utcnow()
    current_user.save()
    return jsonify(_serialize_profile(current_user))


@student_bp.route('/profile/college', methods=['PUT'])
@token_required
def update_college_profile(current_user):
    data = request.get_json() or {}
    old_university_logo_override = str(getattr(current_user, 'universityLogoOverride', '') or '').strip()
    old_college_logo_override = str(getattr(current_user, 'collegeLogoOverride', '') or '').strip()
    ref_map = {
        'university': University,
        'college': College,
        'degree': Degree,
        'academicDepartment': Department,
        'major': Major,
    }

    for field in ['university', 'college', 'degree', 'academicDepartment', 'major']:
        if field not in data:
            # Field not sent at all — leave the existing value unchanged
            continue

        value = str(data.get(field) or '').strip()

        if value == '':
            # Field explicitly sent as empty or null — clear the reference
            setattr(current_user, field, None)
            continue

        doc = ref_map[field].objects(id=value).first()
        if not doc:
            return jsonify({'message': f'Invalid {field}'}), 400
        setattr(current_user, field, doc)

    selected_degree = getattr(current_user, 'degree', None)
    selected_department = getattr(current_user, 'academicDepartment', None)
    if selected_department and selected_degree:
        department_degree = getattr(selected_department, 'degree', None)
        if _doc_id(department_degree) != _doc_id(selected_degree):
            return jsonify({'message': 'Selected department does not belong to selected degree'}), 400

    for field in ['rollNumber', 'enrollmentNumber']:
        if field in data:
            setattr(current_user, field, str(data.get(field) or '').strip())

    if 'semester' in data:
        current_user.semester = str(data.get('semester') or '').strip()
    if 'department' in data:
        current_user.department = str(data.get('department') or '').strip()

    if 'universityLogoOverride' in data:
        current_user.universityLogoOverride = str(data.get('universityLogoOverride') or '').strip()
    if 'collegeLogoOverride' in data:
        current_user.collegeLogoOverride = str(data.get('collegeLogoOverride') or '').strip()

    current_user.profileCompleted = _is_profile_complete(current_user)
    current_user.updatedAt = datetime.datetime.utcnow()
    current_user.save()

    new_university_logo_override = str(getattr(current_user, 'universityLogoOverride', '') or '').strip()
    new_college_logo_override = str(getattr(current_user, 'collegeLogoOverride', '') or '').strip()
    if old_university_logo_override and old_university_logo_override != new_university_logo_override:
        _delete_upload_file(old_university_logo_override)
    if old_college_logo_override and old_college_logo_override != new_college_logo_override:
        _delete_upload_file(old_college_logo_override)

    return jsonify(_serialize_profile(current_user))


@student_bp.route('/profile/industry', methods=['PUT'])
@token_required
def update_industry_profile(current_user):
    data = request.get_json() or {}

    if 'industry' in data:
        industry_value = str(data.get('industry') or '').strip()
        if industry_value == '':
            # Explicitly sent as empty or null — clear the industry reference
            current_user.industry = None
        else:
            industry_doc = Industry.objects(id=industry_value).first()
            if not industry_doc:
                return jsonify({'message': 'Invalid industry'}), 400
            current_user.industry = industry_doc

    if 'supervisorName' in data:
        current_user.supervisorName = str(data.get('supervisorName') or '').strip()
    if 'supervisorContact' in data:
        current_user.supervisorContact = str(data.get('supervisorContact') or '').strip()

    detail_map = {
        'villageCityName': 'industryVillageCityName',
        'tehsil': 'industryTehsil',
        'district': 'industryDistrict',
        'state': 'industryState',
        'website': 'industryWebsite',
        'gstNumber': 'industryGstNumber',
        'industryDetails': 'industryDetails',
        'industryType': 'industryType',
        'industrySubType': 'industrySubType',
    }
    detail_keys_present = False
    for payload_key, user_attr in detail_map.items():
        if payload_key in data:
            detail_keys_present = True
            setattr(current_user, user_attr, str(data.get(payload_key) or '').strip())

    if 'keyActivities' in data:
        detail_keys_present = True
        raw = data.get('keyActivities')
        if isinstance(raw, list):
            activities = [str(item).strip() for item in raw if str(item).strip()]
        else:
            activities = [
                line.strip() for line in str(raw or '').replace('\r\n', '\n').split('\n')
                if line.strip()
            ]
        current_user.industryKeyActivities = activities

    if detail_keys_present:
        current_user.industryProfileCustomized = True
    elif 'industry' in data:
        # Industry changed but no custom details sent: reset to master defaults.
        current_user.industryProfileCustomized = False
        current_user.industryVillageCityName = ''
        current_user.industryTehsil = ''
        current_user.industryDistrict = ''
        current_user.industryState = ''
        current_user.industryWebsite = ''
        current_user.industryGstNumber = ''
        current_user.industryDetails = ''
        current_user.industryType = ''
        current_user.industrySubType = ''
        current_user.industryKeyActivities = []

    current_user.profileCompleted = _is_profile_complete(current_user)
    current_user.updatedAt = datetime.datetime.utcnow()
    current_user.save()
    return jsonify(_serialize_profile(current_user))

@student_bp.route('/reports', methods=['GET'])
@token_required
def get_my_reports(current_user):
    # Fetch reports for the logged in user
    reports_qs = Report.objects(user=current_user.id).order_by('-createdAt')
    limit, offset = _parse_pagination(default_limit=None, max_limit=500)
    if limit is None:
        reports = reports_qs[offset:] if offset else reports_qs
    else:
        reports = reports_qs[offset: offset + limit]
    result = []
    for r in reports:
        result.append({
            '_id': str(r.id),
            'projectTitle': r.projectTitle,
            'status': r.status,
            'academicYear': r.academicYear,
            'createdAt': r.createdAt.isoformat()
        })
    return jsonify(result)
@student_bp.route('/reports/<report_id>', methods=['GET'])
@token_required
def get_report(current_user, report_id):
    try:
        r = Report.objects(id=report_id, user=current_user.id).first()
        if not r:
            return jsonify({'message': 'Not found'}), 404

        default_cover_logos = _resolve_cover_logos({}, r, request)
            
        return jsonify({
            '_id': str(r.id),
            'projectTitle': r.projectTitle,
            'status': r.status,
            'generatedContent': _sanitize_content_map(r.generatedContent or {}),
            'editedContent': _sanitize_content_map(r.editedContent or {}),
            'generatedTitles': _sanitize_titles_map(r.generatedTitles or {}),
            'defaultCoverLogos': default_cover_logos,
            'sectionImages': r.sectionImages or {},
            'imagesEnabled': _is_images_enabled(r),
            'createdAt': r.createdAt.isoformat()
        })
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@student_bp.route('/reports/<report_id>/content', methods=['PUT'])
@token_required
def update_report_content(current_user, report_id):
    data = request.get_json()
    if not data or 'editedContent' not in data:
        return jsonify({'message': 'No content provided'}), 400
        
    try:
        r = Report.objects(id=report_id, user=current_user.id).first()
        if not r:
            return jsonify({'message': 'Not found'}), 404
            
        r.editedContent = _sanitize_content_map(data['editedContent'])
        r.status = 'edited'
        r.save()
        return jsonify({'message': 'Saved successfully'})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

from flask import render_template, send_file
import io
from utils.pdf import generate_pdf_from_html

@student_bp.route('/reports/<report_id>/pdf-preview', methods=['POST'])
@token_required
def generate_pdf_preview(current_user, report_id):
    from routes.reports import (
        _build_pdf_sections,
        _resolve_cover_logos,
        _resolve_cover_page,
        _resolve_layout_settings,
    )

    data = request.get_json() or {}
    edited_content = data.get('editedContent') if isinstance(data.get('editedContent'), dict) else None

    r = Report.objects(id=report_id, user=current_user.id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    content = edited_content or r.editedContent or r.generatedContent or {}
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
    
    base_url = str(request.host_url).rstrip('/')
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
        download_name=f"{r.projectTitle or 'preview'}.pdf"
    )

@student_bp.route('/reports/<report_id>/images/<section_key>', methods=['POST'])
@token_required
def student_upload_section_image(current_user, report_id, section_key):
    r = Report.objects(id=report_id, user=current_user.id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    file = request.files.get('image')
    if not file or not file.filename:
        return jsonify({'message': 'No file provided'}), 400

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return jsonify({'message': 'Invalid file type. Allowed: jpg, jpeg, png, gif, webp'}), 400

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
        'widthPercent': 100,
    }

    images = dict(r.sectionImages or {})
    section_list = list(images.get(section_key, []))
    section_list.append(image_entry)
    images[section_key] = section_list
    r.sectionImages = images
    r.save()
    return jsonify({'image': image_entry}), 201


@student_bp.route('/reports/<report_id>/images/<section_key>/<filename>', methods=['PUT'])
@token_required
def student_update_section_image(current_user, report_id, section_key, filename):
    r = Report.objects(id=report_id, user=current_user.id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

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


@student_bp.route('/reports/<report_id>/images/<section_key>/<filename>', methods=['DELETE'])
@token_required
def student_delete_section_image(current_user, report_id, section_key, filename):
    r = Report.objects(id=report_id, user=current_user.id).first()
    if not r:
        return jsonify({'message': 'Not found'}), 404

    images = dict(r.sectionImages or {})
    before = list(images.get(section_key, []))
    after = [i for i in before if not (isinstance(i, dict) and i.get('filename') == filename)]

    if len(before) == len(after):
        return jsonify({'message': 'Image not found'}), 404

    images[section_key] = after
    r.sectionImages = images
    r.save()

    filepath = os.path.join(REPORT_IMAGE_UPLOAD_FOLDER, str(report_id), section_key, filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass

    return jsonify({'message': 'Deleted'})


@student_bp.route('/project-titles', methods=['GET'])
@token_required
def get_project_titles(current_user):
    """Return active project titles for a given major. Used by create_report page dropdown."""
    major_id = str(request.args.get('major', '')).strip()
    if not major_id:
        return jsonify([])
    titles = [
        title for title in ProjectTitle.objects(major=major_id).order_by('title')
        if _is_active_record(title)
    ]
    return jsonify([{'_id': str(t.id), 'title': t.title} for t in titles])


@student_bp.route('/video-guides', methods=['GET'])
@token_required
def get_video_guides(current_user):
    """Return active video guides ordered by sortOrder."""
    docs = [doc for doc in VideoGuide.objects().order_by('sortOrder') if _is_active_record(doc)]
    return jsonify([{
        '_id': str(d.id),
        'title': d.title,
        'description': d.description,
        'videoUrl': d.videoUrl,
        'videoType': d.videoType,
        'sortOrder': d.sortOrder,
    } for d in docs])


# ─────────────────────────────────────────────────────────────────
# AI ENHANCE — Resume Builder Field Enhancer
# POST /api/student/ai-enhance
# Takes raw keyword-style text → returns polished professional text
# Uses OpenAI directly (no n8n needed for this small single call)
# ─────────────────────────────────────────────────────────────────

# System prompts per field type.
# Defined at module level so they are created once, not on every request.
_AI_ENHANCE_SYSTEM_PROMPTS = {
    'career_objective': (
        "You are a professional resume writer specializing in Indian university students.\n"
        "Write a concise career objective paragraph (strictly 60-80 words, 2-3 sentences).\n"
        "Rules:\n"
        "- Start with the student's degree or field of study\n"
        "- Mention 2-3 specific skills or areas from their input\n"
        "- End with a clear professional goal or aspiration\n"
        "- Do NOT use cliché words: hardworking, passionate, enthusiastic, dynamic, go-getter\n"
        "- Plain text only. No bullet points. No markdown. No asterisks. No headers.\n"
        "- Professional and confident tone\n"
        "- Output ONLY the career objective text. Nothing else. No preamble, no label."
    ),
    'responsibilities': (
        "You are a professional resume writer specializing in Indian university students.\n"
        "Write exactly 4 strong bullet point job responsibilities for a resume experience section.\n"
        "Rules:\n"
        "- Each bullet point on its own line — exactly 4 lines total\n"
        "- Start each line with a strong action verb: Managed, Developed, Analyzed, Coordinated, "
        "Executed, Handled, Monitored, Assisted, Prepared, Maintained, Reviewed, Supported\n"
        "- Include specific details and context from the student's input\n"
        "- Each line must be 10-18 words maximum. Concise and impactful.\n"
        "- Do NOT add bullet symbols (•, -, *, 1.) — plain text only, one line per responsibility\n"
        "- Output ONLY the 4 lines. Nothing else. No preamble, no label, no intro sentence."
    ),
    'project_description': (
        "You are a professional resume writer specializing in Indian university students.\n"
        "Write exactly 3 strong bullet points describing a project for a resume.\n"
        "Rules:\n"
        "- Exactly 3 lines total, each on its own line\n"
        "- Line 1: What the project does or what problem it solves\n"
        "- Line 2: Technologies used, tools, frameworks, or methods\n"
        "- Line 3: Your role, outcome, or key achievement from the project\n"
        "- Start each line with a strong action verb: Built, Developed, Designed, "
        "Implemented, Created, Engineered, Integrated, Deployed\n"
        "- Each line 10-16 words maximum\n"
        "- Do NOT add bullet symbols — plain text, one line per point\n"
        "- Output ONLY the 3 lines. Nothing else. No preamble, no label."
    ),
    'volunteering_description': (
        "You are a professional resume writer specializing in Indian university students.\n"
        "Write exactly 3 strong bullet points describing volunteering contributions for a resume.\n"
        "Rules:\n"
        "- Exactly 3 lines total, each on its own line\n"
        "- Focus on: people helped, events organized, skills demonstrated, impact created\n"
        "- Start each line with strong action verbs: Organized, Assisted, Coordinated, "
        "Supported, Led, Facilitated, Volunteered, Managed, Contributed, Participated\n"
        "- Each line 10-16 words maximum\n"
        "- Do NOT add bullet symbols — plain text, one line per point\n"
        "- Output ONLY the 3 lines. Nothing else. No preamble, no label."
    ),
}

_AI_ENHANCE_VALID_TYPES = set(_AI_ENHANCE_SYSTEM_PROMPTS.keys())


def _build_ai_enhance_user_prompt(field_type, raw_text, context):
    """Build the user-facing prompt for each field type with relevant context."""
    ctx = context if isinstance(context, dict) else {}

    if field_type == 'career_objective':
        degree   = str(ctx.get('degree', '')   or '').strip()
        major    = str(ctx.get('major', '')    or '').strip()
        name     = str(ctx.get('studentName', '') or '').strip()
        return (
            f"Student's rough notes: \"{raw_text}\"\n"
            f"Degree: {degree or 'Not specified'}\n"
            f"Major/Specialization: {major or 'Not specified'}\n"
            f"Student Name: {name or 'Not specified'}\n\n"
            "Write a professional career objective for this student's resume."
        )

    elif field_type == 'responsibilities':
        position    = str(ctx.get('position', '')    or '').strip()
        company     = str(ctx.get('companyName', '') or '').strip()
        return (
            f"Position/Role: {position or 'Intern / Trainee'}\n"
            f"Company/Organization: {company or 'Not specified'}\n"
            f"Student's rough notes: \"{raw_text}\"\n\n"
            "Write 4 professional resume bullet points for the job responsibilities section."
        )

    elif field_type == 'project_description':
        title = str(ctx.get('projectTitle', '') or '').strip()
        return (
            f"Project Title: {title or 'Not specified'}\n"
            f"Student's rough notes: \"{raw_text}\"\n\n"
            "Write 3 professional resume bullet points describing this project."
        )

    elif field_type == 'volunteering_description':
        org  = str(ctx.get('organizationName', '') or '').strip()
        role = str(ctx.get('role', '')             or '').strip()
        return (
            f"Organization: {org or 'Not specified'}\n"
            f"Role/Position: {role or 'Volunteer'}\n"
            f"Student's rough notes: \"{raw_text}\"\n\n"
            "Write 3 professional resume bullet points for the volunteering contributions."
        )

    return f"Student's rough notes: \"{raw_text}\"\n\nEnhance this for a professional resume."


def _clean_ai_enhance_output(raw_output, field_type):
    """
    Clean GPT response:
    - Strip markdown bold/italic formatting
    - Remove any bullet symbols GPT added despite instructions
    - For bullet-type fields: return newline-separated plain lines
    - For career_objective: return a single clean paragraph
    """
    text = str(raw_output or '').strip()

    # Remove markdown formatting GPT sometimes adds despite instructions
    text = text.replace('**', '').replace('__', '')   # bold
    text = text.replace('*', '').replace('_', '')     # italic
    text = text.replace('`', '')                      # code

    # Remove surrounding quotes if GPT wrapped the whole output
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    if field_type == 'career_objective':
        # Single paragraph — collapse any newlines into spaces
        text = re.sub(r'\s*\n\s*', ' ', text)
        text = re.sub(r'\s{2,}', ' ', text)
        return text.strip()

    else:
        # Bullet-type fields — split by newlines, clean each line
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remove any leading bullet symbols GPT added
            line = re.sub(r'^[-•\*\u2022]\s*', '', line)          # dash, bullet, asterisk
            line = re.sub(r'^\d+[\.\)]\s*', '', line)              # numbered: "1. " or "1) "
            line = line.strip()
            if len(line) > 3:   # skip tiny fragments
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)


@student_bp.route('/ai-enhance', methods=['POST'])
@token_required
def ai_enhance_resume_field(current_user):
    """
    AI Enhance endpoint for Resume Builder description fields.

    Request JSON:
    {
        "fieldType": "career_objective" | "responsibilities" |
                     "project_description" | "volunteering_description",
        "rawText": "student's rough notes or keywords",
        "context": {
            // career_objective:
            "degree": "Bachelor of Commerce",
            "major": "Accounting",
            "studentName": "Jeel",
            // responsibilities:
            "position": "Sales Intern",
            "companyName": "XYZ Corp",
            // project_description:
            "projectTitle": "Online Library System",
            // volunteering_description:
            "organizationName": "NSS Unit 42",
            "role": "Event Coordinator"
        }
    }

    Response JSON (success):
    {
        "success": true,
        "enhanced": "Enhanced professional text here...",
        "fieldType": "career_objective"
    }

    Response JSON (error):
    {
        "success": false,
        "error": "Human readable error message"
    }
    """
    # ── Parse request ─────────────────────────────────────────────
    data       = request.get_json(silent=True) or {}
    field_type = str(data.get('fieldType', '') or '').strip()
    raw_text   = str(data.get('rawText',   '') or '').strip()
    context    = data.get('context', {})

    # ── Validate field type ───────────────────────────────────────
    if field_type not in _AI_ENHANCE_VALID_TYPES:
        return jsonify({
            'success': False,
            'error': f"Invalid fieldType. Must be one of: {', '.join(sorted(_AI_ENHANCE_VALID_TYPES))}"
        }), 400

    # ── Validate raw text ─────────────────────────────────────────
    if not raw_text:
        return jsonify({
            'success': False,
            'error': 'Please write something first before using AI Enhance.'
        }), 400

    if len(raw_text) < 3:
        return jsonify({
            'success': False,
            'error': 'Input is too short. Please write at least a few words.'
        }), 400

    if len(raw_text) > 2000:
        return jsonify({
            'success': False,
            'error': 'Input is too long. Please keep it under 2000 characters.'
        }), 400

    # ── Load OpenAI config ────────────────────────────────────────
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    model   = os.getenv('OPENAI_MODEL', 'gpt-4.1').strip()

    if not api_key or api_key == 'sk-your-key-here':
        return jsonify({
            'success': False,
            'error': 'AI service is not configured. Please contact support.'
        }), 503

    # ── Build prompts ─────────────────────────────────────────────
    system_prompt = _AI_ENHANCE_SYSTEM_PROMPTS[field_type]
    user_prompt   = _build_ai_enhance_user_prompt(field_type, raw_text, context)

    # ── Call OpenAI API ───────────────────────────────────────────
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            temperature=0.5,   # lower = more consistent, professional output
            max_tokens=400,    # enough for 4-5 bullets or one paragraph
            timeout=25,        # seconds — fail fast if OpenAI is slow
        )

        raw_output = response.choices[0].message.content or ''

    except Exception as api_err:
        err_str = str(api_err)
        # Give the student a friendly message without exposing internal details
        if 'api_key' in err_str.lower() or 'authentication' in err_str.lower():
            msg = 'AI service authentication failed. Please contact support.'
        elif 'timeout' in err_str.lower() or 'timed out' in err_str.lower():
            msg = 'AI took too long to respond. Please try again.'
        elif 'rate_limit' in err_str.lower():
            msg = 'AI service is busy. Please wait a moment and try again.'
        elif 'connection' in err_str.lower() or 'network' in err_str.lower():
            msg = 'Network error reaching AI service. Please check your connection.'
        else:
            msg = 'AI enhancement failed. Please try again.'

        import sys
        print(f"[AI Enhance] OpenAI error for fieldType={field_type!r}: {err_str}", file=sys.stderr)
        return jsonify({'success': False, 'error': msg}), 502

    # ── Clean and return ──────────────────────────────────────────
    enhanced = _clean_ai_enhance_output(raw_output, field_type)

    if not enhanced:
        return jsonify({
            'success': False,
            'error': 'AI returned empty output. Please try again with more detail.'
        }), 502

    return jsonify({
        'success': True,
        'enhanced': enhanced,
        'fieldType': field_type,
    })

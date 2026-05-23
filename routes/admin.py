import os
import io
import re
import jwt
import datetime as dt
from datetime import datetime
import secrets
import smtplib
import ssl
import shutil
from email.message import EmailMessage
from flask import Blueprint, request, jsonify, render_template, send_file
from functools import wraps
from routes.auth import token_required, generate_token
from models.user import User
from models.report import Report
from models.degree import Degree, DegreePolicy
from models.major import Major, ReportPolicy, ReportSection
from models.university import University
from models.college import College
from models.industry import Industry
from models.payment import Payment
from models.service import Service
from models.internship_type import InternshipType
from models.project_title import ProjectTitle
from models.department import Department
from models.work_keyword import WorkKeyword
from models.resume import Resume
from models.career_objective import CareerObjective
from models.resume_keyword import ResumeKeyword
from models.blog_post import BlogPost
from models.faq_item import FaqItem
from models import AssignmentSession, AssignmentPrompt

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin privilege required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated


def _obj_id(doc):
    if doc is None:
        return None
    if isinstance(doc, dict):
        dict_id = doc.get('_id') or doc.get('id')
        return str(dict_id) if dict_id is not None else None
    if isinstance(doc, (str, int)):
        return str(doc)
    # Custom ORM documents may expose ID via `id` or raw `_data['id']`
    direct_id = getattr(doc, 'id', None)
    if direct_id is not None:
        return str(direct_id)
    raw_data = getattr(doc, '_data', None) or {}
    raw_id = raw_data.get('id')
    return str(raw_id) if raw_id is not None else None


def _norm_id(value):
    return str(value) if value is not None else None


def _safe_ref(doc):
    if not doc:
        return None
    try:
        return {'_id': _obj_id(doc), 'name': getattr(doc, 'name', None)}
    except Exception:
        return None


def _field(doc, name, default=None):
    if doc is None:
        return default
    if isinstance(doc, dict):
        return doc.get(name, default)

    try:
        value = getattr(doc, name)
    except Exception:
        value = None
    if value is not None:
        return value

    raw_data = getattr(doc, '_data', None) or {}
    return raw_data.get(name, default)


def _json_list_response(items, total=None, limit=None, offset=None):
    if limit is None and offset is None:
        return jsonify(items)
    return jsonify({
        'items': items,
        'total': len(items) if total is None else total,
        'limit': limit,
        'offset': offset,
    })


def _serialize_degree(doc):
    policy = getattr(doc, 'policy', None)
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'isActive': _field(doc, 'isActive', True),
        'policy': {
            'reportLanguage': policy.reportLanguage if policy else 'English',
            'reportContentType': policy.reportContentType if policy else 'Text',
            'allowedLanguages': list(policy.allowedLanguages or []) if policy else [],
            'generationInstruction': policy.generationInstruction if policy else '',
            'aiPromptContext': policy.aiPromptContext if policy else '',
            'strictLanguageOnly': bool(policy.strictLanguageOnly) if policy else False,
            'imagesRequired': bool(policy.imagesRequired) if policy else False,
        },
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_major(doc):
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'degree': {
            '_id': _obj_id(doc.degree),
            'name': _field(doc.degree, 'name', None),
        } if getattr(doc, 'degree', None) else None,
        'department': {
            '_id': _obj_id(doc.department),
            'name': _field(doc.department, 'name', None),
        } if getattr(doc, 'department', None) else None,
        'reportLanguage': _field(doc, 'reportLanguage', 'English'),
        'reportContentType': _field(doc, 'reportContentType', 'Text'),
        'aiPromptContext': _field(doc, 'aiPromptContext', ''),
        'reportPolicy': doc.reportPolicy.to_mongo().to_dict() if getattr(doc, 'reportPolicy', None) else {},
        'reportSections': [
            {
                'key': s.key,
                'title': s.title,
                'description': s.description,
            } for s in (doc.reportSections or [])
        ],
        'isActive': _field(doc, 'isActive', True),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_project_title(doc):
    return {
        '_id': _obj_id(doc),
        'title': _field(doc, 'title', ''),
        'major': {
            '_id': _obj_id(doc.major),
            'name': getattr(doc.major, 'name', None),
        } if doc.major else None,
        'degree': {
            '_id': _obj_id(doc.degree),
            'name': getattr(doc.degree, 'name', None),
        } if getattr(doc, 'degree', None) else None,
        'isActive': _field(doc, 'isActive', True),
        'createdBy': {
            '_id': _obj_id(doc.createdBy),
            'name': getattr(doc.createdBy, 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
        'updatedAt': _field(doc, 'updatedAt', None).isoformat() if _field(doc, 'updatedAt', None) else None,
    }


def _serialize_work_keyword(doc):
    major_obj = getattr(doc, 'major', None)
    return {
        '_id': _obj_id(doc),
        'keyword': doc.keyword,
        'industryType': doc.industryType,
        'jobProfile': doc.jobProfile,
        'major': {
            '_id': _obj_id(major_obj),
            'name': getattr(major_obj, 'name', ''),
        } if major_obj else None,
        'sortOrder': doc.sortOrder,
        'isActive': doc.isActive,
        'createdAt': doc.createdAt.isoformat() if doc.createdAt else None,
    }


def _serialize_career_objective(doc):
    return {
        '_id': _obj_id(doc),
        'text': getattr(doc, 'text', ''),
        'major': {
            '_id': _obj_id(getattr(doc, 'major', None)),
            'name': getattr(getattr(doc, 'major', None), 'name', None),
        } if getattr(doc, 'major', None) else None,
        'isActive': getattr(doc, 'isActive', True),
        'approvalStatus': getattr(doc, 'approvalStatus', 'approved'),
        'rejectionReason': getattr(doc, 'rejectionReason', ''),
        'createdBy': {
            '_id': _obj_id(getattr(doc, 'createdBy', None)),
            'name': getattr(getattr(doc, 'createdBy', None), 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'createdAt': getattr(doc, 'createdAt', None).isoformat() if getattr(doc, 'createdAt', None) else None,
    }


def _serialize_resume_keyword(doc):
    return {
        '_id': _obj_id(doc),
        'keyword': getattr(doc, 'keyword', ''),
        'category': getattr(doc, 'category', ''),
        'major': {
            '_id': _obj_id(getattr(doc, 'major', None)),
            'name': getattr(getattr(doc, 'major', None), 'name', None),
        } if getattr(doc, 'major', None) else None,
        'industryType': getattr(doc, 'industryType', ''),
        'jobProfile': getattr(doc, 'jobProfile', ''),
        'sortOrder': getattr(doc, 'sortOrder', 0),
        'isActive': getattr(doc, 'isActive', True),
        'createdAt': getattr(doc, 'createdAt', None).isoformat() if getattr(doc, 'createdAt', None) else None,
    }


def _serialize_resume(doc, include_full=False):
    user_obj = getattr(doc, 'user', None)

    def _serialize_embedded_list(items):
        out = []
        for item in items or []:
            if hasattr(item, 'to_mongo'):
                try:
                    out.append(item.to_mongo().to_dict())
                    continue
                except Exception:
                    pass
            out.append(item)
        return out

    base = {
        '_id': _obj_id(doc),
        'title': _field(doc, 'title', ''),
        'fullName': _field(doc, 'fullName', ''),
        'email': _field(doc, 'email', ''),
        'phone': _field(doc, 'phone', ''),
        'status': _field(doc, 'status', 'draft'),
        'downloadCount': int(_field(doc, 'downloadCount', 0) or 0),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
        'updatedAt': _field(doc, 'updatedAt', None).isoformat() if _field(doc, 'updatedAt', None) else None,
        'user': _safe_ref(user_obj),
        'userName': _field(user_obj, 'name', '') if user_obj else '',
        'userEmail': _field(user_obj, 'email', '') if user_obj else '',
        'major': _safe_ref(getattr(user_obj, 'major', None)),
        'degree': _safe_ref(getattr(user_obj, 'degree', None)),
        'college': _safe_ref(getattr(user_obj, 'college', None)),
        'university': _safe_ref(getattr(user_obj, 'university', None)),
    }

    if include_full:
        base.update({
            'address': _field(doc, 'address', ''),
            'photoUrl': _field(doc, 'photoUrl', ''),
            'linkedinUrl': _field(doc, 'linkedinUrl', ''),
            'githubUrl': _field(doc, 'githubUrl', ''),
            'careerObjectiveRaw': _field(doc, 'careerObjectiveRaw', ''),
            'careerObjectiveEnhanced': _field(doc, 'careerObjectiveEnhanced', ''),
            'education': _serialize_embedded_list(_field(doc, 'education', []) or []),
            'experience': _serialize_embedded_list(_field(doc, 'experience', []) or []),
            'projects': _serialize_embedded_list(_field(doc, 'projects', []) or []),
            'volunteering': _serialize_embedded_list(_field(doc, 'volunteering', []) or []),
            'certifications': _serialize_embedded_list(_field(doc, 'certifications', []) or []),
            'languages': _serialize_embedded_list(_field(doc, 'languages', []) or []),
            'skills': list(_field(doc, 'skills', []) or []),
            'technicalSkills': list(_field(doc, 'technicalSkills', []) or []),
            'coursework': list(_field(doc, 'coursework', []) or []),
            'personalSkills': list(_field(doc, 'personalSkills', []) or []),
            'errorMessage': _field(doc, 'errorMessage', ''),
        })

    return base


def _normalize_text(value):
    text = re.sub(r'[^\w\s]+', ' ', str(value or ''))
    return re.sub(r'\s+', ' ', text).strip().casefold()


def _find_existing_by_name(model_cls, name, extra_match=None):
    target_name = _normalize_text(name)
    if not target_name:
        return None

    for doc in model_cls.objects():
        if _normalize_text(getattr(doc, 'name', '')) != target_name:
            continue
        if extra_match and not extra_match(doc):
            continue
        return doc
    return None


def _resolve_reference_doc(model_cls, value):
    raw_value = value
    if isinstance(value, dict):
        raw_value = value.get('_id') or value.get('id') or value.get('name')

    raw_value = str(raw_value or '').strip()
    if not raw_value:
        return None

    doc = model_cls.objects(id=raw_value).first()
    if doc:
        return doc

    return _find_existing_by_name(model_cls, raw_value)


def _normalize_major_payload(data):
    normalized = {}

    if 'name' in data:
        normalized['name'] = str(data.get('name') or '').strip()

    if 'degree' in data:
        raw_degree = data.get('degree')
        degree_id = None
        if isinstance(raw_degree, dict):
            degree_id = raw_degree.get('_id') or raw_degree.get('id')
        else:
            degree_id = raw_degree

        degree_id = str(degree_id or '').strip()
        if not degree_id:
            raise ValueError('Degree is required')

        degree_doc = Degree.objects(id=degree_id).first()
        if not degree_doc:
            raise ValueError('Invalid degree')
        normalized['degree'] = degree_doc

    if 'department' in data:
        raw_dept = data.get('department')
        if not raw_dept:
            normalized['department'] = None
        else:
            dept_id = str(raw_dept if not isinstance(raw_dept, dict) else (raw_dept.get('_id') or raw_dept.get('id') or '')).strip()
            if dept_id:
                dept_doc = Department.objects(id=dept_id).first()
                normalized['department'] = dept_doc
            else:
                normalized['department'] = None

    if 'reportLanguage' in data:
        normalized['reportLanguage'] = str(data.get('reportLanguage') or 'English').strip() or 'English'

    if 'reportContentType' in data:
        normalized['reportContentType'] = str(data.get('reportContentType') or 'Text').strip() or 'Text'

    if 'aiPromptContext' in data:
        normalized['aiPromptContext'] = str(data.get('aiPromptContext') or '')

    if 'isActive' in data:
        normalized['isActive'] = bool(data.get('isActive'))

    if 'reportPolicy' in data:
        raw_policy = data.get('reportPolicy')
        if raw_policy is None:
            normalized['reportPolicy'] = ReportPolicy()
        elif isinstance(raw_policy, dict):
            # Remove fields that are no longer needed
            filtered_policy = {k: v for k, v in raw_policy.items() if k not in ['allowedScriptsRegex', 'fallbackMessage']}
            normalized['reportPolicy'] = ReportPolicy(**filtered_policy)
        else:
            raise ValueError('reportPolicy must be an object')

    if 'reportSections' in data:
        raw_sections = data.get('reportSections')
        if raw_sections is None:
            normalized['reportSections'] = []
        elif not isinstance(raw_sections, list):
            raise ValueError('reportSections must be an array')
        else:
            sections = []
            for idx, raw in enumerate(raw_sections):
                if not isinstance(raw, dict):
                    raise ValueError(f'reportSections[{idx}] must be an object')

                key = str(raw.get('key') or '').strip()
                title = str(raw.get('title') or '').strip()
                description = str(raw.get('description') or '')

                if not key or not title:
                    raise ValueError(f'reportSections[{idx}] requires key and title')

                sections.append(ReportSection(key=key, title=title, description=description))
            normalized['reportSections'] = sections

    return normalized


def _serialize_university(doc):
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'villageCityName': _field(doc, 'villageCityName', ''),
        'tehsil': _field(doc, 'tehsil', ''),
        'district': _field(doc, 'district', ''),
        'state': _field(doc, 'state', ''),
        'website': _field(doc, 'website', ''),
        'logo': _field(doc, 'logo', ''),
        'approvalStatus': getattr(doc, 'approvalStatus', 'approved'),
        'rejectionReason': getattr(doc, 'rejectionReason', ''),
        'createdBy': {
            '_id': _obj_id(doc.createdBy),
            'name': _field(doc.createdBy, 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'isActive': _field(doc, 'isActive', True),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_college(doc):
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'university': {
            '_id': _obj_id(doc.university),
            'name': _field(doc.university, 'name', None),
        } if doc.university else None,
        'villageCityName': _field(doc, 'villageCityName', ''),
        'tehsil': _field(doc, 'tehsil', ''),
        'district': _field(doc, 'district', ''),
        'state': _field(doc, 'state', ''),
        'logo': _field(doc, 'logo', ''),
        'website': _field(doc, 'website', ''),
        'approvalStatus': getattr(doc, 'approvalStatus', 'approved'),
        'rejectionReason': getattr(doc, 'rejectionReason', ''),
        'createdBy': {
            '_id': _obj_id(doc.createdBy),
            'name': _field(doc.createdBy, 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'isActive': _field(doc, 'isActive', True),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_industry(doc):
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'villageCityName': _field(doc, 'villageCityName', ''),
        'tehsil': _field(doc, 'tehsil', ''),
        'district': _field(doc, 'district', ''),
        'state': _field(doc, 'state', ''),
        'logo': _field(doc, 'logo', ''),
        'website': _field(doc, 'website', ''),
        'gstNumber': _field(doc, 'gstNumber', ''),
        'industryDetails': _field(doc, 'industryDetails', ''),
        'industryType': _field(doc, 'industryType', ''),
        'industrySubType': _field(doc, 'industrySubType', ''),
        'keyActivities': _field(doc, 'keyActivities', []) or [],
        'approvalStatus': getattr(doc, 'approvalStatus', 'approved'),
        'rejectionReason': getattr(doc, 'rejectionReason', ''),
        'createdBy': {
            '_id': _obj_id(doc.createdBy),
            'name': _field(doc.createdBy, 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'isVerified': _field(doc, 'isVerified', False),
        'isActive': _field(doc, 'isActive', True),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_user(doc, last_report=None):
    """Serialize a User document. Optionally include last report status."""
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'email': _field(doc, 'email', ''),
        'role': _field(doc, 'role', ''),
        'isActive': _field(doc, 'isActive', True),
        'villageCityName': _field(doc, 'villageCityName', ''),
        'state': _field(doc, 'state', ''),
        'phone': _field(doc, 'phone', ''),
        'whatsapp': _field(doc, 'whatsapp', ''),
        'tehsil': _field(doc, 'tehsil', ''),
        'district': _field(doc, 'district', ''),
        'gender': _field(doc, 'gender', ''),
        'semester': _field(doc, 'semester', ''),
        'department': _field(doc, 'department', ''),
        'rollNumber': _field(doc, 'rollNumber', ''),
        'enrollmentNumber': _field(doc, 'enrollmentNumber', ''),
        'supervisorName': _field(doc, 'supervisorName', ''),
        'supervisorContact': _field(doc, 'supervisorContact', ''),
        'profileCompleted': _field(doc, 'profileCompleted', False),
        'college': _safe_ref(doc.college),
        'university': _safe_ref(doc.university),
        'industry': _safe_ref(doc.industry),
        'degree': _safe_ref(doc.degree),
        'major': _safe_ref(doc.major),
        'lastReportStatus': last_report.status if last_report else 'none',
        'lastReportId': _obj_id(last_report) if last_report else None,
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_service(doc):
    return {
        '_id': _obj_id(doc),
        'name': _field(doc, 'name', ''),
        'type': _field(doc, 'type', ''),
        'price': _field(doc, 'price', 0),
        'gstIncluded': _field(doc, 'gstIncluded', False),
        'gstPercent': _field(doc, 'gstPercent', 0),
        'freeLimit': _field(doc, 'freeLimit', 0),
        'degreePricing': [
            {
                'degree': {
                    '_id': _obj_id(item.degree),
                    'name': item.degree.name,
                } if item.degree else None,
                'price': item.price,
            } for item in (doc.degreePricing or [])
        ],
        'description': _field(doc, 'description', ''),
        'isActive': _field(doc, 'isActive', True),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_payment(doc):
    service_val = _field(doc, 'service', None)
    if hasattr(service_val, 'id'):
        service_data = {
            '_id': str(service_val.id),
            'name': getattr(service_val, 'name', ''),
            'type': getattr(service_val, 'type', ''),
        }
    else:
        service_data = service_val

    return {
        '_id': _obj_id(doc),
        'user': {
            '_id': _obj_id(doc.user),
            'name': _field(doc.user, 'name', None),
            'email': _field(doc.user, 'email', None),
            'villageCityName': _field(doc.user, 'villageCityName', None),
            'state': _field(doc.user, 'state', None),
            'college': _safe_ref(getattr(doc.user, 'college', None)),
        } if doc.user else None,
        'service': service_data,
        'amount': _field(doc, 'amount', 0),
        'gstAmount': _field(doc, 'gstAmount', 0),
        'totalAmount': _field(doc, 'totalAmount', 0),
        'status': _field(doc, 'status', ''),
        'paymentMethod': _field(doc, 'paymentMethod', ''),
        'transactionId': _field(doc, 'transactionId', ''),
        'createdAt': _field(doc, 'createdAt', None).isoformat() if _field(doc, 'createdAt', None) else None,
    }


def _serialize_report(doc):
    university_ref = _safe_ref(doc.university)
    if not university_ref and getattr(doc, 'user', None):
        # Backward compatibility: some old reports may not store university on report.
        university_ref = _safe_ref(getattr(doc.user, 'university', None))

    return {
        '_id': _obj_id(doc),
        'projectTitle': doc.projectTitle,
        'status': doc.status,
        'createdAt': doc.createdAt.isoformat() if doc.createdAt else None,
        'user': {
            '_id': _obj_id(doc.user),
            'name': getattr(doc.user, 'name', None),
            'email': getattr(doc.user, 'email', None),
        } if doc.user else None,
        'degree': _safe_ref(doc.degree),
        'major': _safe_ref(doc.major),
        'college': _safe_ref(doc.college),
        'university': university_ref,
        'industry': _safe_ref(doc.industry),
    }


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats(current_user):
    total_users = User.objects(role='student').count()
    total_reports = Report.objects.count()
    total_degrees = Degree.objects.count()
    total_majors = Major.objects.count()
    total_universities = University.objects.count()
    total_colleges = College.objects.count()
    total_industries = Industry.objects.count()
    generated = Report.objects(status__in=['generated', 'edited', 'final']).count()
    pending = Report.objects(status__in=['pending', 'generating']).count()
    total_payments = Payment.objects(status='completed').count()
    total_types = InternshipType.objects(isActive=True).count()
    total_revenue = sum([(p.totalAmount or 0) for p in Payment.objects(status='completed')])

    return jsonify({
        'totalUsers': total_users,
        'totalReports': total_reports,
        'totalDegrees': total_degrees,
        'totalMajors': total_majors,
        'totalUniversities': total_universities,
        'totalColleges': total_colleges,
        'totalIndustries': total_industries,
        'generated': generated,
        'pending': pending,
        'totalPayments': total_payments,
        'totalTypes': total_types,
        'totalRevenue': total_revenue,
    })


@admin_bp.route('/degrees', methods=['GET'])
@admin_required
def get_degrees(current_user):
    q = str(request.args.get('q', '')).strip()
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    docs = list(Degree.objects().order_by('name'))
    if q:
        q_lower = q.lower()
        docs = [d for d in docs if q_lower in str(getattr(d, 'name', '') or '').lower()]

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    return _json_list_response([_serialize_degree(d) for d in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/degrees', methods=['POST'])
@admin_required
def create_degree(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'Name is required'}), 400

    doc = Degree(name=name, isActive=data.get('isActive', True))
    doc.save()
    return jsonify(_serialize_degree(doc)), 201


@admin_bp.route('/degrees/<degree_id>', methods=['PUT'])
@admin_required
def update_degree(current_user, degree_id):
    doc = Degree.objects(id=degree_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    if 'name' in data:
        doc.name = str(data['name']).strip()
    if 'isActive' in data:
        doc.isActive = data['isActive']

    if 'policy' in data and isinstance(data['policy'], dict):
        p = data['policy']
        if not doc.policy:
            doc.policy = DegreePolicy()
        doc.policy.reportLanguage = str(p.get('reportLanguage', 'English')).strip() or 'English'
        doc.policy.reportContentType = str(p.get('reportContentType', 'Text')).strip() or 'Text'
        doc.policy.allowedLanguages = [str(v).strip() for v in (p.get('allowedLanguages') or []) if str(v).strip()]
        doc.policy.generationInstruction = str(p.get('generationInstruction', '')).strip()
        doc.policy.aiPromptContext = str(p.get('aiPromptContext', '')).strip()
        doc.policy.strictLanguageOnly = bool(p.get('strictLanguageOnly', False))
        doc.policy.imagesRequired = bool(p.get('imagesRequired', False))
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_degree(doc))


@admin_bp.route('/degrees/<degree_id>', methods=['DELETE'])
@admin_required
def delete_degree(current_user, degree_id):
    Major.objects(degree=degree_id).delete()
    Degree.objects(id=degree_id).delete()
    return jsonify({'message': 'Deleted with all majors'})


@admin_bp.route('/majors', methods=['GET'])
@admin_required
def get_majors(current_user):
    q = str(request.args.get('q', '')).strip()
    degree = str(request.args.get('degree', '')).strip()
    department = str(request.args.get('department', '')).strip()

    filters = {}
    if q:
        filters['name__icontains'] = q
    if degree:
        filters['degree'] = degree
    if department:
        filters['department'] = department

    docs = Major.objects(**filters).order_by('name')
    return jsonify([_serialize_major(m) for m in docs])


@admin_bp.route('/majors/<major_id>', methods=['GET'])
@admin_required
def get_major(current_user, major_id):
    doc = Major.objects(id=major_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    return jsonify(_serialize_major(doc))


@admin_bp.route('/majors', methods=['POST'])
@admin_required
def create_major(current_user):
    data = request.get_json() or {}
    if not data.get('name') or not data.get('degree'):
        return jsonify({'message': 'Missing required fields'}), 400

    try:
        payload = _normalize_major_payload(data)
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400

    degree_doc = payload.get('degree')

    inherited_language = 'English'
    inherited_content_type = 'Text'
    inherited_ai_context = ''
    inherited_policy = ReportPolicy()

    if degree_doc and getattr(degree_doc, 'policy', None):
        dp = degree_doc.policy
        inherited_language = dp.reportLanguage or 'English'
        inherited_content_type = dp.reportContentType or 'Text'
        inherited_ai_context = dp.aiPromptContext or ''
        inherited_policy = ReportPolicy(
            strictLanguageOnly=dp.strictLanguageOnly or False,
            allowedLanguages=list(dp.allowedLanguages or []),
            generationInstruction=dp.generationInstruction or '',
            imagesRequired=dp.imagesRequired or False,
        )

    doc = Major(
        name=payload.get('name', str(data.get('name') or '').strip()),
        degree=degree_doc,
        department=payload.get('department', None),
        reportLanguage=payload.get('reportLanguage', inherited_language),
        reportContentType=payload.get('reportContentType', inherited_content_type),
        aiPromptContext=payload.get('aiPromptContext', inherited_ai_context),
        isActive=payload.get('isActive', True),
    )
    if 'reportPolicy' in payload:
        doc.reportPolicy = payload['reportPolicy']
    else:
        doc.reportPolicy = inherited_policy
    if 'reportSections' in payload:
        doc.reportSections = payload['reportSections']

    doc.save()
    return jsonify(_serialize_major(doc)), 201


@admin_bp.route('/majors/<major_id>', methods=['PUT'])
@admin_required
def update_major(current_user, major_id):
    doc = Major.objects(id=major_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    try:
        payload = _normalize_major_payload(data)
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400

    for field in [
        'name',
        'degree',
        'department',
        'reportLanguage',
        'reportContentType',
        'aiPromptContext',
        'reportPolicy',
        'reportSections',
        'isActive',
    ]:
        if field in payload:
            setattr(doc, field, payload[field])
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_major(doc))


@admin_bp.route('/majors/<major_id>', methods=['DELETE'])
@admin_required
def delete_major(current_user, major_id):
    Major.objects(id=major_id).delete()
    return jsonify({'message': 'Deleted'})


def _serialize_department(doc):
    return {
        '_id': _obj_id(doc),
        'name': getattr(doc, 'name', ''),
        'degree': {
            '_id': _obj_id(getattr(doc, 'degree', None)),
            'name': _field(getattr(doc, 'degree', None), 'name', None),
        } if getattr(doc, 'degree', None) else None,
        'approvalStatus': getattr(doc, 'approvalStatus', 'approved'),
        'rejectionReason': getattr(doc, 'rejectionReason', ''),
        'createdBy': {
            '_id': _obj_id(getattr(doc, 'createdBy', None)),
            'name': _field(getattr(doc, 'createdBy', None), 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'isActive': getattr(doc, 'isActive', True),
        'createdAt': getattr(doc, 'createdAt', None).isoformat() if getattr(doc, 'createdAt', None) else None,
    }


@admin_bp.route('/departments', methods=['GET'])
@admin_required
def get_departments(current_user):
    q = str(request.args.get('q', '')).strip()
    degree = str(request.args.get('degree', '')).strip()
    status_filter = str(request.args.get('status', '')).strip().lower()
    pending_only = str(request.args.get('pending', '')).strip().lower() in ('1', 'true', 'yes', 'on')
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    docs = list(Department.objects().order_by('name'))
    if q:
        q_lower = q.lower()
        docs = [d for d in docs if q_lower in str(getattr(d, 'name', '') or '').lower()]
    if degree:
        def _dept_degree_matches(d, target_degree_id):
            raw = getattr(d, 'degree', None)
            if raw is None:
                return False

            # Works when reference is resolved to a document.
            extracted = _obj_id(raw)
            if extracted is not None and str(extracted) == str(target_degree_id):
                return True

            # Fallback for adapters storing raw FK in payload.
            raw_data = getattr(d, '_data', {}) or {}
            raw_val = raw_data.get('degree')
            if raw_val is not None and str(raw_val) == str(target_degree_id):
                return True

            # Last resort when reference is scalar (e.g., int FK).
            return str(raw) == str(target_degree_id)

        docs = [d for d in docs if _dept_degree_matches(d, degree)]
    if pending_only:
        status_filter = 'pending'
    if status_filter in ('approved', 'pending', 'rejected'):
        docs = [d for d in docs if getattr(d, 'approvalStatus', 'approved') == status_filter]

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    return _json_list_response([_serialize_department(d) for d in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/departments', methods=['POST'])
@admin_required
def create_department(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    degree = _resolve_reference_doc(Degree, data.get('degree'))

    if not name or not degree:
        return jsonify({'message': 'name and degree are required'}), 400

    existing = _find_existing_by_name(
        Department,
        name,
        extra_match=lambda doc: str(_obj_id(getattr(doc, 'degree', None))) == str(_obj_id(degree)),
    )
    if existing:
        return jsonify(_serialize_department(existing)), 200

    doc = Department(
        name=name,
        degree=degree,
        createdBy=current_user.id,
        approvalStatus=str(data.get('approvalStatus', 'approved') or 'approved').strip().lower() or 'approved',
        isActive=bool(data.get('isActive', True)),
    )
    doc.save()
    return jsonify(_serialize_department(doc)), 201


@admin_bp.route('/departments/<department_id>', methods=['PUT'])
@admin_required
def update_department(current_user, department_id):
    doc = Department.objects(id=department_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    for field in ['name', 'degree', 'isActive', 'approvalStatus', 'rejectionReason']:
        if field in data:
            if field == 'degree':
                resolved = _resolve_reference_doc(Degree, data[field])
                if not resolved and data[field]:
                    return jsonify({'message': 'Invalid degree'}), 400
                doc.degree = resolved
            else:
                setattr(doc, field, data[field])

    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_department(doc))


@admin_bp.route('/departments/<department_id>', methods=['DELETE'])
@admin_required
def delete_department(current_user, department_id):
    Department.objects(id=department_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/departments/<department_id>/approve', methods=['PUT'])
@admin_required
def approve_department(current_user, department_id):
    doc = Department.objects(id=department_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.approvalStatus = 'approved'
    doc.rejectionReason = ''
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_department(doc))


@admin_bp.route('/departments/<department_id>/reject', methods=['PUT'])
@admin_required
def reject_department(current_user, department_id):
    doc = Department.objects(id=department_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    doc.approvalStatus = 'rejected'
    doc.rejectionReason = str(data.get('reason', '')).strip()
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_department(doc))


@admin_bp.route('/project-titles', methods=['GET'])
@admin_required
def get_project_titles(current_user):
    degree_id = str(request.args.get('degree', '')).strip()
    major_id = str(request.args.get('major', '')).strip()
    q = str(request.args.get('q', '')).strip()

    docs = list(ProjectTitle.objects().order_by('title'))
    if degree_id:
        docs = [doc for doc in docs if str(_obj_id(getattr(doc, 'degree', None)) or '') == degree_id or str(_obj_id(getattr(getattr(doc, 'major', None), 'degree', None)) or '') == degree_id]
    if major_id:
        docs = [doc for doc in docs if str(_obj_id(doc.major)) == major_id]
    if q:
        q_lower = q.lower()
        docs = [doc for doc in docs if q_lower in str(doc.title or '').lower()]

    return jsonify([_serialize_project_title(doc) for doc in docs])


@admin_bp.route('/project-titles', methods=['POST'])
@admin_required
def create_project_title(current_user):
    data = request.get_json() or {}
    title = str(data.get('title', '')).strip()
    major = _resolve_reference_doc(Major, data.get('major'))
    if not title or not major:
        return jsonify({'message': 'title and major are required'}), 400

    degree = _resolve_reference_doc(Degree, data.get('degree')) or getattr(major, 'degree', None)

    existing = next(
        (
            doc for doc in ProjectTitle.objects()
            if _normalize_text(doc.title) == _normalize_text(title)
            and str(_obj_id(doc.major)) == str(_obj_id(major))
        ),
        None,
    )
    if existing:
        return jsonify(_serialize_project_title(existing)), 200

    doc = ProjectTitle(
        title=title,
        major=major,
        degree=degree,
        createdBy=current_user.id,
        isActive=bool(data.get('isActive', True)),
    )
    doc.save()
    return jsonify(_serialize_project_title(doc)), 201


@admin_bp.route('/project-titles/<project_title_id>', methods=['PUT'])
@admin_required
def update_project_title(current_user, project_title_id):
    doc = ProjectTitle.objects(id=project_title_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    if 'title' in data:
        title = str(data.get('title', '')).strip()
        if not title:
            return jsonify({'message': 'title cannot be empty'}), 400
        duplicate = next(
            (
                item for item in ProjectTitle.objects()
                if str(getattr(item, 'id', '')) != str(doc.id)
                and _normalize_text(getattr(item, 'title', '')) == _normalize_text(title)
                and str(_obj_id(getattr(item, 'major', None))) == str(_obj_id(getattr(doc, 'major', None)))
            ),
            None,
        )
        if duplicate:
            return jsonify({'message': 'A project title with this name already exists for this major'}), 409
        doc.title = title

    if 'major' in data:
        major = _resolve_reference_doc(Major, data.get('major'))
        if not major:
            return jsonify({'message': 'Invalid major'}), 400
        doc.major = major
        if 'degree' not in data:
            doc.degree = getattr(major, 'degree', None)

    if 'degree' in data:
        degree = _resolve_reference_doc(Degree, data.get('degree'))
        if data.get('degree') and not degree:
            return jsonify({'message': 'Invalid degree'}), 400
        doc.degree = degree

    if 'isActive' in data:
        doc.isActive = bool(data.get('isActive'))

    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_project_title(doc))


@admin_bp.route('/project-titles/<project_title_id>', methods=['DELETE'])
@admin_required
def delete_project_title(current_user, project_title_id):
    ProjectTitle.objects(id=project_title_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/universities', methods=['GET'])
@admin_required
def get_universities(current_user):
    q = str(request.args.get('q', '')).strip()
    status_filter = str(request.args.get('status', '')).strip().lower()
    pending_only = str(request.args.get('pending', '')).strip().lower() in ('1', 'true', 'yes', 'on')
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    docs = list(University.objects().order_by('name'))
    if q:
        q_lower = q.lower()
        docs = [doc for doc in docs if q_lower in str(doc.name or '').lower()]
    if pending_only:
        status_filter = 'pending'
    if status_filter in ('approved', 'pending', 'rejected'):
        docs = [doc for doc in docs if getattr(doc, 'approvalStatus', 'approved') == status_filter]
    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]
    return _json_list_response([_serialize_university(d) for d in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/universities', methods=['POST'])
@admin_required
def create_university(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'Name is required'}), 400

    existing = _find_existing_by_name(University, name)
    if existing:
        return jsonify(_serialize_university(existing)), 200

    doc = University(
        name=name,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        logo=str(data.get('logo', '')).strip(),
        createdBy=current_user.id,
        isVerified=bool(data.get('isVerified', True)),
        isActive=bool(data.get('isActive', True)),
        approvalStatus=str(data.get('approvalStatus', 'approved') or 'approved').strip().lower() or 'approved',
        rejectionReason=str(data.get('rejectionReason', '')).strip(),
    )
    doc.save()
    return jsonify(_serialize_university(doc)), 201


@admin_bp.route('/universities/merge', methods=['POST'])
@admin_required
def merge_universities(current_user):
    data = request.get_json() or {}
    source_id = data.get('sourceId')
    target_id = data.get('targetId')
    if not source_id or not target_id:
        return jsonify({'message': 'sourceId and targetId are required'}), 400

    College.objects(university=source_id).update(set__university=target_id)
    User.objects(university=source_id).update(set__university=target_id)
    Report.objects(university=source_id).update(set__university=target_id)
    University.objects(id=source_id).delete()
    return jsonify({'message': 'Merged successfully'})


@admin_bp.route('/universities/<university_id>', methods=['PUT'])
@admin_required
def update_university(current_user, university_id):
    doc = University.objects(id=university_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    for field in [
        'name', 'villageCityName', 'tehsil', 'district', 'state',
        'website', 'logo', 'isVerified', 'isActive', 'approvalStatus', 'rejectionReason'
    ]:
        if field in data:
            setattr(doc, field, data[field])
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_university(doc))


@admin_bp.route('/universities/<university_id>', methods=['DELETE'])
@admin_required
def delete_university(current_user, university_id):
    University.objects(id=university_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/universities/<university_id>/approve', methods=['PUT'])
@admin_required
def approve_university(current_user, university_id):
    doc = University.objects(id=university_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.approvalStatus = 'approved'
    doc.isVerified = True
    doc.rejectionReason = ''
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_university(doc))


@admin_bp.route('/universities/<university_id>/reject', methods=['PUT'])
@admin_required
def reject_university(current_user, university_id):
    doc = University.objects(id=university_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    doc.approvalStatus = 'rejected'
    doc.isVerified = False
    doc.rejectionReason = str(data.get('reason', '')).strip()
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_university(doc))


@admin_bp.route('/colleges', methods=['GET'])
@admin_required
def get_colleges(current_user):
    q = str(request.args.get('q', '')).strip()
    university_id = str(request.args.get('university', '')).strip()
    status_filter = str(request.args.get('status', '')).strip().lower()
    pending_only = str(request.args.get('pending', '')).strip().lower() in ('1', 'true', 'yes', 'on')
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    docs = list(College.objects().order_by('name'))
    if q:
        q_lower = q.lower()
        docs = [doc for doc in docs if q_lower in str(getattr(doc, 'name', '') or '').lower()]
    if university_id:
        docs = [doc for doc in docs if str(_obj_id(getattr(doc, 'university', None))) == university_id]
    if pending_only:
        status_filter = 'pending'
    if status_filter in ('approved', 'pending', 'rejected'):
        docs = [doc for doc in docs if getattr(doc, 'approvalStatus', 'approved') == status_filter]

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    return _json_list_response([_serialize_college(d) for d in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/colleges', methods=['POST'])
@admin_required
def create_college(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    university = _resolve_reference_doc(University, data.get('university'))
    if not name or not university:
        return jsonify({'message': 'name and university are required'}), 400

    existing = _find_existing_by_name(
        College,
        name,
        extra_match=lambda doc: str(_obj_id(doc.university)) == str(_obj_id(university)),
    )
    if existing:
        return jsonify(_serialize_college(existing)), 200

    doc = College(
        name=name,
        university=university,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        logo=str(data.get('logo', '')).strip(),
        createdBy=current_user.id,
        isVerified=bool(data.get('isVerified', True)),
        isActive=bool(data.get('isActive', True)),
        approvalStatus=str(data.get('approvalStatus', 'approved') or 'approved').strip().lower() or 'approved',
        rejectionReason=str(data.get('rejectionReason', '')).strip(),
    )
    doc.save()
    return jsonify(_serialize_college(doc)), 201


@admin_bp.route('/colleges/merge', methods=['POST'])
@admin_required
def merge_colleges(current_user):
    data = request.get_json() or {}
    source_id = data.get('sourceId')
    target_id = data.get('targetId')
    if not source_id or not target_id:
        return jsonify({'message': 'sourceId and targetId are required'}), 400

    User.objects(college=source_id).update(set__college=target_id)
    Report.objects(college=source_id).update(set__college=target_id)
    College.objects(id=source_id).delete()
    return jsonify({'message': 'Merged successfully'})


@admin_bp.route('/colleges/<college_id>', methods=['PUT'])
@admin_required
def update_college(current_user, college_id):
    doc = College.objects(id=college_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    for field in [
        'name', 'university', 'villageCityName', 'tehsil', 'district',
        'state', 'website', 'logo', 'isVerified', 'isActive', 'approvalStatus', 'rejectionReason'
    ]:
        if field in data:
            if field == 'university':
                resolved = _resolve_reference_doc(University, data[field])
                if not resolved:
                    return jsonify({'message': 'Invalid university'}), 400
                doc.university = resolved
            else:
                setattr(doc, field, data[field])
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_college(doc))


@admin_bp.route('/colleges/<college_id>', methods=['DELETE'])
@admin_required
def delete_college(current_user, college_id):
    College.objects(id=college_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/colleges/<college_id>/approve', methods=['PUT'])
@admin_required
def approve_college(current_user, college_id):
    doc = College.objects(id=college_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.approvalStatus = 'approved'
    doc.isVerified = True
    doc.rejectionReason = ''
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_college(doc))


@admin_bp.route('/colleges/<college_id>/reject', methods=['PUT'])
@admin_required
def reject_college(current_user, college_id):
    doc = College.objects(id=college_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    doc.approvalStatus = 'rejected'
    doc.isVerified = False
    doc.rejectionReason = str(data.get('reason', '')).strip()
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_college(doc))


@admin_bp.route('/industries', methods=['GET'])
@admin_required
def get_industries(current_user):
    q = str(request.args.get('q', '')).strip()
    status_filter = str(request.args.get('status', '')).strip()  # 'pending', 'approved', 'rejected'
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None
    filters = {}
    if q:
        filters['name__icontains'] = q
    if status_filter in ('pending', 'approved', 'rejected'):
        filters['approvalStatus'] = status_filter
    docs = Industry.objects(**filters).order_by('name')
    total = docs.count()
    docs = list(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]
    return _json_list_response([_serialize_industry(d) for d in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/industries', methods=['POST'])
@admin_required
def create_industry(current_user):
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'message': 'Name is required'}), 400

    existing = _find_existing_by_name(Industry, name)
    if existing:
        return jsonify(_serialize_industry(existing)), 200

    doc = Industry(
        name=name,
        villageCityName=str(data.get('villageCityName', '')).strip(),
        tehsil=str(data.get('tehsil', '')).strip(),
        district=str(data.get('district', '')).strip(),
        state=str(data.get('state', '')).strip(),
        website=str(data.get('website', '')).strip(),
        logo=str(data.get('logo', '')).strip(),
        gstNumber=str(data.get('gstNumber', '')).strip(),
        industryDetails=str(data.get('industryDetails', '')).strip(),
        industryType=str(data.get('industryType', '')).strip(),
        industrySubType=str(data.get('industrySubType', '')).strip(),
        keyActivities=data.get('keyActivities', []) if isinstance(data.get('keyActivities', []), list) else [],
        createdBy=current_user.id,
        approvalStatus=str(data.get('approvalStatus', 'approved') or 'approved').strip().lower() or 'approved',
        isVerified=bool(data.get('isVerified', True)),
        isActive=bool(data.get('isActive', True)),
    )
    doc.save()
    return jsonify(_serialize_industry(doc)), 201


@admin_bp.route('/industries/merge', methods=['POST'])
@admin_required
def merge_industries(current_user):
    data = request.get_json() or {}
    source_id = data.get('sourceId')
    target_id = data.get('targetId')
    if not source_id or not target_id:
        return jsonify({'message': 'sourceId and targetId are required'}), 400

    User.objects(industry=source_id).update(set__industry=target_id)
    Report.objects(industry=source_id).update(set__industry=target_id)
    Industry.objects(id=source_id).delete()
    return jsonify({'message': 'Merged successfully'})


@admin_bp.route('/industries/<industry_id>', methods=['PUT'])
@admin_required
def update_industry(current_user, industry_id):
    doc = Industry.objects(id=industry_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    for field in [
        'name', 'villageCityName', 'tehsil', 'district', 'state',
        'website', 'logo', 'isVerified', 'isActive',
        'gstNumber', 'industryDetails', 'industryType', 'industrySubType', 'keyActivities', 'approvalStatus', 'rejectionReason'
    ]:
        if field in data:
            setattr(doc, field, data[field])
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_industry(doc))


@admin_bp.route('/industries/<industry_id>', methods=['DELETE'])
@admin_required
def delete_industry(current_user, industry_id):
    Industry.objects(id=industry_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/industries/<industry_id>/approve', methods=['PUT'])
@admin_required
def approve_industry(current_user, industry_id):
    """Approve a student-submitted industry."""
    doc = Industry.objects(id=industry_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.approvalStatus = 'approved'
    doc.isVerified = True
    doc.rejectionReason = ''
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_industry(doc))


@admin_bp.route('/industries/<industry_id>/reject', methods=['PUT'])
@admin_required
def reject_industry(current_user, industry_id):
    """Reject a student-submitted industry with optional reason."""
    doc = Industry.objects(id=industry_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    doc.approvalStatus = 'rejected'
    doc.rejectionReason = str(data.get('reason', '')).strip()
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_industry(doc))


@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users(current_user):
    q = str(request.args.get('q', '')).strip()
    university_id = str(request.args.get('university', '')).strip()
    degree_id = str(request.args.get('degree', '')).strip()
    report_status_filter = str(request.args.get('report_status', '')).strip()
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    users_qs = User.objects(role='student')

    if q:
        users_qs = users_qs.filter(__raw__={
            '$or': [
                {'name': {'$regex': q, '$options': 'i'}},
                {'email': {'$regex': q, '$options': 'i'}},
            ]
        })

    docs = list(users_qs.order_by('-createdAt'))

    # Apply university and degree filters in Python (custom ORM limitation)
    if university_id:
        docs = [u for u in docs if u._data.get('university') == university_id]
    if degree_id:
        docs = [u for u in docs if u._data.get('degree') == degree_id]

    # Fetch last report for each user efficiently
    all_reports = list(Report.objects().order_by('-createdAt'))

    # Build a map: normalized user_id -> most recent Report object
    last_report_map = {}
    for r in all_reports:
        uid = _norm_id(r._data.get('user'))
        if uid and uid not in last_report_map:
            last_report_map[uid] = r

    # Apply report status filter
    if report_status_filter:
        valid_statuses = {
            'generated': ['generated', 'edited', 'final'],
            'pending': ['pending', 'generating'],
            'error': ['error'],
            'none': [],
        }
        if report_status_filter == 'none':
            docs = [
                u for u in docs
                if _norm_id(u._data.get('id', getattr(u, 'id', None))) not in last_report_map
            ]
        elif report_status_filter in valid_statuses:
            target_statuses = valid_statuses[report_status_filter]
            docs = [
                u for u in docs
                if (
                    last_report_map.get(_norm_id(u._data.get('id', getattr(u, 'id', None)))) and
                    last_report_map[_norm_id(u._data.get('id', getattr(u, 'id', None)))].status in target_statuses
                )
            ]

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    result = []
    for u in docs:
        uid = _norm_id(u._data.get('id', getattr(u, 'id', None)))
        lr = last_report_map.get(uid)
        result.append(_serialize_user(u, last_report=lr))

    if pagination_requested:
        return jsonify({'items': result, 'total': total, 'limit': limit, 'offset': offset})
    return jsonify(result)


@admin_bp.route('/users/<user_id>/toggle', methods=['PUT'])
@admin_required
def toggle_user(current_user, user_id):
    doc = User.objects(id=user_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.isActive = not bool(doc.isActive)
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_user(doc))


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_user, user_id):
    User.objects(id=user_id).delete()
    Report.objects(user=user_id).delete()
    Payment.objects(user=user_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/users/<user_id>', methods=['GET'])
@admin_required
def get_user(current_user, user_id):
    doc = User.objects(id=user_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    return jsonify(_serialize_user(doc))


@admin_bp.route('/users/<user_id>/impersonate', methods=['POST'])
@admin_required
def impersonate_user(current_user, user_id):
    """Generate a short-lived 15-min JWT for admin to log in as a student."""
    target = User.objects(id=user_id).first()
    if not target or target.role != 'student':
        return jsonify({'message': 'Not found or not a student'}), 404

    if not target.isActive:
        return jsonify({'message': 'Cannot impersonate a disabled account'}), 403

    secret = os.getenv('JWT_SECRET')
    if not secret:
        return jsonify({'message': 'JWT_SECRET not configured'}), 500

    payload = {
        'userId': str(target.id),
        'role': target.role,
        'impersonatedBy': str(current_user.id),
        'exp': dt.datetime.utcnow() + dt.timedelta(minutes=15),
        'iat': dt.datetime.utcnow(),
    }
    token = jwt.encode(payload, secret, algorithm='HS256')

    print(f"[IMPERSONATE] Admin '{current_user.email}' impersonating student '{target.email}'")

    return jsonify({
        'token': token,
        'studentName': target.name,
        'studentEmail': target.email,
        'expiresInMinutes': 15,
    }), 200


@admin_bp.route('/users/<user_id>/generate-report', methods=['POST'])
@admin_required
def admin_generate_report(current_user, user_id):
    """Admin triggers report generation on behalf of a student.
    Accepts same payload as POST /api/reports/ but uses target_user's profile data.
    Required fields in body: major, projectTitle, briefDescription
    """
    from routes.reports import _resolve_public_base_url

    target_user = User.objects(id=user_id).first()
    if not target_user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}
    major_id = str(data.get('major', '') or '').strip()
    project_title = str(data.get('projectTitle', '') or '').strip()
    brief_description = str(data.get('briefDescription', '') or '').strip()

    if not major_id or not project_title or not brief_description:
        return jsonify({'message': 'major, projectTitle, and briefDescription are required'}), 400

    major_doc = Major.objects(id=major_id).first()
    if not major_doc:
        return jsonify({'message': 'Major not found'}), 404

    industry_id = str(data.get('industry', '') or '').strip()
    if not industry_id and target_user.industry:
        industry_id = str(target_user.industry.id)

    report = Report(
        user=target_user.id,
        degree=major_doc.degree.id if major_doc.degree else None,
        major=major_doc.id,
        college=target_user.college.id if target_user.college else None,
        university=target_user.university.id if target_user.university else None,
        industry=industry_id or None,
        rollNumber=data.get('rollNumber', getattr(target_user, 'rollNumber', '')),
        studentEmail=target_user.email,
        reportLanguage=major_doc.reportLanguage,
        projectTitle=project_title,
        internshipTitle=str(data.get('internshipTitle', '') or ''),
        academicYear=str(data.get('academicYear', '') or ''),
        duration=str(data.get('duration', '') or ''),
        startDate=str(data.get('startDate', '') or ''),
        endDate=str(data.get('endDate', '') or ''),
        positionTitle=str(data.get('positionTitle', '') or ''),
        supervisorName=str(data.get('supervisorName', '') or getattr(target_user, 'supervisorName', '')),
        supervisorContact=str(data.get('supervisorContact', '') or getattr(target_user, 'supervisorContact', '')),
        briefDescription=brief_description,
        keySkills=str(data.get('keySkills', '') or ''),
        status='generating',
    )
    report.save()

    import requests as req_lib

    base_backend_url = _resolve_public_base_url(request)
    col_name = target_user.college.name if target_user.college else ''
    uni_name = target_user.university.name if target_user.university else ''
    ind_doc = Industry.objects(id=industry_id).first() if industry_id else None
    ind_name = ind_doc.name if ind_doc else ''

    payload = {
        'reportId': str(report.id),
        'callbackUrl': f"{base_backend_url}/api/reports/{report.id}/generated",
        'student': {
            'name': target_user.name,
            'email': target_user.email,
            'rollNumber': report.rollNumber,
            'enrollmentNumber': getattr(target_user, 'enrollmentNumber', ''),
            'villageCityName': getattr(target_user, 'villageCityName', ''),
            'district': getattr(target_user, 'district', ''),
            'state': getattr(target_user, 'state', ''),
        },
        'college': {
            'name': col_name,
            'villageCityName': target_user.college.villageCityName if target_user.college else '',
            'district': target_user.college.district if target_user.college else '',
            'state': target_user.college.state if target_user.college else '',
            'website': target_user.college.website if target_user.college else '',
        },
        'university': {
            'name': uni_name,
            'villageCityName': target_user.university.villageCityName if target_user.university else '',
            'district': target_user.university.district if target_user.university else '',
            'state': target_user.university.state if target_user.university else '',
        },
        'industry': {
            'name': ind_name,
            'villageCityName': ind_doc.villageCityName if ind_doc else '',
            'district': ind_doc.district if ind_doc else '',
            'state': ind_doc.state if ind_doc else '',
            'website': ind_doc.website if ind_doc else '',
            'supervisorName': report.supervisorName,
        },
        'academic': {
            'degree': major_doc.degree.name if major_doc.degree else '',
            'major': major_doc.name,
            'university': uni_name,
            'college': col_name,
        },
        'internship': {
            'industryName': ind_name,
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
        },
        'reportConfig': {
            'language': report.reportLanguage,
            'contentType': major_doc.reportContentType,
            'policy': major_doc.reportPolicy.to_mongo().to_dict() if major_doc.reportPolicy else {},
            'aiContext': major_doc.aiPromptContext,
            'sections': [
                {'key': s.key, 'title': s.title, 'description': s.description}
                for s in (major_doc.reportSections or [])
            ],
        },
    }

    n8n_url = os.getenv('N8N_WEBHOOK_URL')
    callback_secret = os.getenv('N8N_CALLBACK_SECRET', '')
    if n8n_url:
        try:
            headers = {'Content-Type': 'application/json'}
            if callback_secret:
                headers['X-Callback-Secret'] = callback_secret
            n8n_response = req_lib.post(n8n_url, json=payload, headers=headers, timeout=120)
            if not n8n_response.ok:
                report.status = 'error'
                report.errorMessage = f'Generation service returned error: {n8n_response.status_code}'
                report.save()
        except req_lib.exceptions.Timeout:
            pass
        except Exception as e:
            report.status = 'error'
            report.errorMessage = f'Generation service error: {str(e)}'
            report.save()

    return jsonify({'message': 'Generating...', 'reportId': str(report.id)}), 201


def _send_email_with_attachment(recipient_email, recipient_name, subject, body_text, attachment_bytes, attachment_filename):
    """Send an email with a PDF attachment. Uses the same SMTP config as auth.py."""
    smtp_host = os.getenv('SMTP_HOST', '').strip()
    smtp_port = int(str(os.getenv('SMTP_PORT', '587')).strip() or '587')
    smtp_user = os.getenv('SMTP_USER', '').strip()
    smtp_pass = os.getenv('SMTP_PASS', '').strip()
    sender_email = os.getenv('SMTP_FROM_EMAIL', smtp_user).strip()
    sender_name = os.getenv('SMTP_FROM_NAME', 'ReportGen').strip() or 'ReportGen'
    use_ssl_env = str(os.getenv('SMTP_USE_SSL', 'false')).strip().lower()
    use_ssl = use_ssl_env in ('1', 'true', 'yes', 'on')

    if not smtp_host or not sender_email:
        raise RuntimeError('SMTP is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL in .env')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f'{sender_name} <{sender_email}>'
    msg['To'] = recipient_email
    msg.set_content(body_text)
    msg.add_attachment(attachment_bytes, maintype='application', subtype='pdf',
                       filename=attachment_filename)

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context(), timeout=30) as server:
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)


@admin_bp.route('/reports/<report_id>/email', methods=['POST'])
@admin_required
def email_report(current_user, report_id):
    """Generate the PDF for a report and email it to the student."""
    from routes.reports import (
        _build_pdf_sections, _resolve_cover_logos, _resolve_layout_settings,
        _resolve_public_base_url, _sanitize_content_map,
    )
    from utils.pdf import generate_pdf_from_html

    r = Report.objects(id=report_id).first()
    if not r:
        return jsonify({'message': 'Report not found'}), 404

    student = r.user
    if not student:
        return jsonify({'message': 'Report has no associated student'}), 400

    recipient_email = str(student.email or '').strip()
    if not recipient_email:
        return jsonify({'message': 'Student has no email address'}), 400

    content = r.editedContent or r.generatedContent or {}
    if not content:
        return jsonify({'message': 'Report has no generated content yet'}), 400

    try:
        sections = _build_pdf_sections(r, content, request)
        cover_logos = _resolve_cover_logos(content, r, request)
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
            layout_settings=layout_settings,
            sections=sections,
        )
        base_url = _resolve_public_base_url(request)
        html_string = html_string.replace('<head>', f'<head><base href="{base_url}/">', 1)
        pdf_bytes = generate_pdf_from_html(
            html_string, base_url=base_url,
            student_name=student.name if student else 'Student',
        )
    except Exception as e:
        return jsonify({'message': f'PDF generation failed: {str(e)}'}), 500

    file_name = f"{(r.projectTitle or 'Internship_Report').strip()}.pdf"
    subject = f"Your Internship Report ΓÇö {r.projectTitle or 'Report'}"
    body = (
        f"Dear {student.name or 'Student'},\n\n"
        f"Your internship report '{r.projectTitle}' is attached.\n\n"
        f"Regards,\nReportGen Team"
    )

    try:
        _send_email_with_attachment(
            recipient_email=recipient_email,
            recipient_name=student.name or 'Student',
            subject=subject,
            body_text=body,
            attachment_bytes=pdf_bytes,
            attachment_filename=file_name,
        )
    except RuntimeError as e:
        return jsonify({'message': str(e), 'smtpConfigured': False}), 503
    except Exception as e:
        return jsonify({'message': f'Failed to send email: {str(e)}'}), 500

    return jsonify({'message': f'Report sent successfully to {recipient_email}'}), 200


@admin_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(current_user, user_id):
    """Generate a secure random password, set it, and email it to the student."""
    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({'message': 'Not found'}), 404

    # Generate a password that meets validation rules: 8+ chars, 1 uppercase, 1 digit
    raw = secrets.token_urlsafe(10)
    # Ensure it has at least one uppercase letter and one digit (token_urlsafe is alphanumeric + symbols)
    new_password = 'R' + raw[:4] + '7' + raw[4:]

    target.set_password(new_password)
    target.updatedAt = datetime.utcnow()
    target.save()

    # Try to email the new password
    smtp_configured = bool(os.getenv('SMTP_HOST', '').strip() and os.getenv('SMTP_FROM_EMAIL', '').strip())
    email_sent = False
    if smtp_configured and target.email:
        try:
            smtp_host = os.getenv('SMTP_HOST', '').strip()
            smtp_port = int(str(os.getenv('SMTP_PORT', '587')).strip() or '587')
            smtp_user = os.getenv('SMTP_USER', '').strip()
            smtp_pass = os.getenv('SMTP_PASS', '').strip()
            sender_email = os.getenv('SMTP_FROM_EMAIL', smtp_user).strip()
            sender_name = os.getenv('SMTP_FROM_NAME', 'ReportGen Support').strip() or 'ReportGen Support'
            use_ssl = str(os.getenv('SMTP_USE_SSL', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')

            msg = EmailMessage()
            msg['Subject'] = 'Your ReportGen Password Has Been Reset'
            msg['From'] = f'{sender_name} <{sender_email}>'
            msg['To'] = target.email
            msg.set_content(
                f"Hi {target.name or 'Student'},\n\n"
                f"Your password has been reset by an administrator.\n\n"
                f"New Password: {new_password}\n\n"
                f"Please login and change your password immediately.\n\n"
                f"Regards,\nReportGen Team"
            )

            if use_ssl:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context(), timeout=20) as server:
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            email_sent = True
        except Exception as e:
            print(f"[RESET_PASSWORD] Email failed: {e}")

    return jsonify({
        'message': 'Password reset successfully',
        'newPassword': new_password,
        'emailSent': email_sent,
        'studentEmail': target.email,
    }), 200


@admin_bp.route('/users/<user_id>/email', methods=['PUT'])
@admin_required
def update_user_email(current_user, user_id):
    """Update a student's email address with uniqueness validation."""
    import re

    target = User.objects(id=user_id).first()
    if not target:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    new_email = str(data.get('email', '') or '').strip().lower()

    if not new_email:
        return jsonify({'message': 'Email is required'}), 400

    email_pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, new_email):
        return jsonify({'message': 'Invalid email format'}), 400

    existing = User.objects(email=new_email).first()
    if existing and str(existing.id) != str(target.id):
        return jsonify({'message': 'Email is already registered to another account'}), 409

    old_email = target.email
    target.email = new_email
    target.updatedAt = datetime.utcnow()
    target.save()

    print(f"[UPDATE_EMAIL] Admin '{current_user.email}' changed student email: '{old_email}' ΓåÆ '{new_email}'")

    return jsonify({
        'message': 'Email updated successfully',
        'oldEmail': old_email,
        'newEmail': new_email,
    }), 200


@admin_bp.route('/services', methods=['GET'])
@admin_required
def get_services(current_user):
    docs = Service.objects().order_by('name')
    return jsonify([_serialize_service(s) for s in docs])


@admin_bp.route('/services', methods=['POST'])
@admin_required
def create_service(current_user):
    data = request.get_json() or {}
    if not data.get('name') or not data.get('type'):
        return jsonify({'message': 'name and type are required'}), 400

    doc = Service(
        name=data['name'],
        type=data['type'],
        price=float(data.get('price', data.get('basePrice', 0)) or 0),
        gstIncluded=bool(data.get('gstIncluded', False)),
        gstPercent=int(data.get('gstPercent', 18) or 18),
        freeLimit=int(data.get('freeLimit', 0) or 0),
        description=data.get('description', ''),
        isActive=bool(data.get('isActive', True)),
    )
    if 'degreePricing' in data and isinstance(data['degreePricing'], list):
        doc.degreePricing = data['degreePricing']

    doc.save()
    return jsonify(_serialize_service(doc)), 201


@admin_bp.route('/services/<service_id>', methods=['PUT'])
@admin_required
def update_service(current_user, service_id):
    doc = Service.objects(id=service_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    data = request.get_json() or {}
    field_map = {
        'name': 'name',
        'type': 'type',
        'price': 'price',
        'basePrice': 'price',
        'gstIncluded': 'gstIncluded',
        'gstPercent': 'gstPercent',
        'freeLimit': 'freeLimit',
        'description': 'description',
        'degreePricing': 'degreePricing',
        'isActive': 'isActive',
    }
    for in_field, model_field in field_map.items():
        if in_field in data:
            setattr(doc, model_field, data[in_field])
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_service(doc))


@admin_bp.route('/services/<service_id>', methods=['DELETE'])
@admin_required
def delete_service(current_user, service_id):
    Service.objects(id=service_id).delete()
    return jsonify({'message': 'Deleted'})


# ── Admin: Assignment Studio ──────────────────────────────────────────────

@admin_bp.route('/assignments', methods=['GET'])
@admin_required
def admin_get_assignments(current_user=None):
    """List all assignment sessions (admin view — no user filter)."""
    try:
        all_sessions = list(AssignmentSession.objects())
        sessions = [s for s in all_sessions if not bool(getattr(s, 'isDeleted', False))]

        # Filters
        filter_type = request.args.get('type', '').strip()
        filter_status = request.args.get('status', '').strip()
        q = request.args.get('q', '').strip().lower()
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        if filter_type:
            sessions = [s for s in sessions if getattr(s, 'assignmentType', '') == filter_type]
        if filter_status:
            sessions = [s for s in sessions if getattr(s, 'status', '') == filter_status]
        if q:
            sessions = [s for s in sessions if q in str(getattr(s, 'title', '') or '').lower()]

        sessions.sort(key=lambda s: getattr(s, 'createdAt', datetime.min), reverse=True)
        total = len(sessions)
        page = sessions[offset: offset + limit]

        def _admin_serialize(s):
            user_obj = getattr(s, 'user', None)
            user_name = ''
            user_email = ''
            if user_obj:
                try:
                    user_name = str(getattr(user_obj, 'name', '') or '')
                    user_email = str(getattr(user_obj, 'email', '') or '')
                except Exception:
                    pass
            base = {
                '_id': str(getattr(s, 'id', '') or ''),
                'title': str(getattr(s, 'title', '') or ''),
                'assignmentType': str(getattr(s, 'assignmentType', '') or ''),
                'status': str(getattr(s, 'status', 'draft') or 'draft'),
                'wordCountCurrent': int(getattr(s, 'wordCountCurrent', 0) or 0),
                'wordCountTarget': int(getattr(s, 'wordCountTarget', 0) or 0),
                'generationCount': int(getattr(s, 'generationCount', 0) or 0),
                'universityName': str(getattr(s, 'universityName', '') or ''),
                'userName': user_name,
                'userEmail': user_email,
                'createdAt': s.createdAt.isoformat() if getattr(s, 'createdAt', None) else '',
            }
            return base

        return jsonify({
            'items': [_admin_serialize(s) for s in page],
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@admin_bp.route('/assignments/stats', methods=['GET'])
@admin_required
def admin_assignment_stats(current_user=None):
    """Aggregate statistics for Assignment Studio dashboard."""
    try:
        all_sessions = list(AssignmentSession.objects())
        sessions = [s for s in all_sessions if not bool(getattr(s, 'isDeleted', False))]

        by_type = {}
        by_status = {}
        total = len(sessions)

        for s in sessions:
            t = str(getattr(s, 'assignmentType', 'other') or 'other')
            st = str(getattr(s, 'status', 'draft') or 'draft')
            by_type[t] = by_type.get(t, 0) + 1
            by_status[st] = by_status.get(st, 0) + 1

        return jsonify({
            'total': total,
            'byType': by_type,
            'byStatus': by_status,
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@admin_bp.route('/assignments/<session_id>', methods=['DELETE'])
@admin_required
def admin_delete_assignment(current_user, session_id):
    s = AssignmentSession.objects(id=session_id).first()
    if not s:
        return jsonify({'message': 'Not found'}), 404
    try:
        s.isDeleted = True
        s.updatedAt = datetime.utcnow()
        s.save()
    except Exception:
        pass
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/assignments/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_assignments(current_user):
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400

    deleted = 0
    for session_id in ids:
        s = AssignmentSession.objects(id=session_id).first()
        if not s:
            continue
        try:
            s.isDeleted = True
            s.updatedAt = datetime.utcnow()
            s.save()
            deleted += 1
        except Exception:
            continue

    return jsonify({'message': f'Deleted {deleted} assignments', 'deleted': deleted})


@admin_bp.route('/assignments/<session_id>/pdf', methods=['GET'])
@admin_required
def admin_assignment_pdf(current_user, session_id):
    from utils.pdf import generate_pdf_from_html
    from routes.student import _serialize_assignment_session, _serialize_profile

    s = AssignmentSession.objects(id=session_id).first()
    if not s:
        return jsonify({'message': 'Not found'}), 404

    sections = list(getattr(s, 'documentSections', []) or [])
    if not sections:
        return jsonify({'message': 'Assignment not yet generated'}), 400

    preview_mode = str(request.args.get('preview', '')).lower() in {'1', 'true', 'yes'}
    html_content = render_template(
        'assignment_pdf_template.html',
        session=_serialize_assignment_session(s, include_sections=True),
        user=_serialize_profile(current_user),
    )
    pdf_bytes = generate_pdf_from_html(html_content)

    safe_title = str(getattr(s, 'title', 'assignment') or 'assignment')
    safe_title = ''.join(c for c in safe_title if c.isalnum() or c in ' _-')[:60].strip().replace(' ', '_')
    filename = f'{safe_title}_assignment.pdf'

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=not preview_mode,
        download_name=filename if not preview_mode else 'preview.pdf',
    )


@admin_bp.route('/assignment-prompts', methods=['GET'])
@admin_required
def admin_get_prompts(current_user=None):
    all_prompts = list(AssignmentPrompt.objects())
    all_prompts.sort(key=lambda p: int(getattr(p, 'sortOrder', 0) or 0))

    def _s(p):
        return {
            '_id': str(getattr(p, 'id', '') or ''),
            'name': str(getattr(p, 'name', '') or ''),
            'assignmentType': str(getattr(p, 'assignmentType', '*') or '*'),
            'triggerKeywords': list(getattr(p, 'triggerKeywords', []) or []),
            'injectedInstruction': str(getattr(p, 'injectedInstruction', '') or ''),
            'sortOrder': int(getattr(p, 'sortOrder', 0) or 0),
            'isActive': bool(getattr(p, 'isActive', True)),
        }

    return jsonify([_s(p) for p in all_prompts]), 200


@admin_bp.route('/assignment-prompts', methods=['POST'])
@admin_required
def admin_create_prompt(current_user=None):
    data = request.get_json(silent=True) or {}
    if not data.get('name') or not data.get('injectedInstruction'):
        return jsonify({'message': 'name and injectedInstruction are required'}), 400
    p = AssignmentPrompt(
        name=str(data['name'])[:200],
        assignmentType=str(data.get('assignmentType', '*') or '*'),
        triggerKeywords=list(data.get('triggerKeywords', []) or []),
        injectedInstruction=str(data['injectedInstruction']),
        sortOrder=int(data.get('sortOrder', 0) or 0),
        isActive=bool(data.get('isActive', True)),
    )
    p.save()
    return jsonify({'success': True, '_id': str(p.id)}), 201


@admin_bp.route('/assignment-prompts/<prompt_id>', methods=['PUT'])
@admin_required
def admin_update_prompt(current_user=None, prompt_id=None):
    p = AssignmentPrompt.objects(id=prompt_id).first()
    if not p:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        p.name = str(data['name'])[:200]
    if 'assignmentType' in data:
        p.assignmentType = str(data['assignmentType'])
    if 'triggerKeywords' in data:
        p.triggerKeywords = list(data['triggerKeywords'] or [])
    if 'injectedInstruction' in data:
        p.injectedInstruction = str(data['injectedInstruction'])
    if 'sortOrder' in data:
        p.sortOrder = int(data['sortOrder'] or 0)
    if 'isActive' in data:
        p.isActive = bool(data['isActive'])
    p.updatedAt = datetime.utcnow()
    p.save()
    return jsonify({'success': True}), 200


@admin_bp.route('/assignment-prompts/<prompt_id>', methods=['DELETE'])
@admin_required
def admin_delete_prompt(current_user=None, prompt_id=None):
    p = AssignmentPrompt.objects(id=prompt_id).first()
    if not p:
        return jsonify({'message': 'Not found'}), 404
    p.delete()
    return jsonify({'success': True}), 200


@admin_bp.route('/assignment-prompts/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_prompts(current_user=None):
        data = request.get_json(silent=True) or {}
        ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
        if not ids:
                return jsonify({'message': 'No IDs provided'}), 400

        deleted = 0
        for prompt_id in ids:
            p = AssignmentPrompt.objects(id=prompt_id).first()
            if not p:
                continue
            try:
                p.delete()
                deleted += 1
            except Exception:
                continue

        return jsonify({'success': True, 'deleted': deleted}), 200



@admin_bp.route('/payments', methods=['GET'])
@admin_required
def get_payments(current_user):
    from_date = str(request.args.get('from', '')).strip()
    to_date = str(request.args.get('to', '')).strip()
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    filters = {}
    created_filter = {}
    if from_date:
        try:
            created_filter['$gte'] = datetime.fromisoformat(from_date)
        except ValueError:
            pass
    if to_date:
        try:
            created_filter['$lte'] = datetime.fromisoformat(to_date)
        except ValueError:
            pass

    if created_filter:
        filters['createdAt'] = created_filter

    docs = list(Payment.objects(__raw__=filters).order_by('-createdAt'))
    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]
    return _json_list_response([_serialize_payment(p) for p in docs], total=total, limit=limit, offset=offset if pagination_requested else None)


@admin_bp.route('/reports', methods=['GET'])
@admin_required
def get_reports(current_user):
    q = str(request.args.get('q', '')).strip().lower()
    status_filter = str(request.args.get('status', '')).strip().lower()
    university_filter = str(request.args.get('university', '')).strip().lower()
    template_filter = str(request.args.get('template', '')).strip().lower()
    from_date = str(request.args.get('from', '')).strip()
    to_date = str(request.args.get('to', '')).strip()
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    docs = list(Report.objects().order_by('-createdAt'))
    if q:
        docs = [doc for doc in docs if q in str(getattr(doc, 'projectTitle', '')).lower() or q in str(getattr(getattr(doc, 'user', None), 'name', '')).lower() or q in str(getattr(getattr(doc, 'user', None), 'email', '')).lower()]
    if status_filter in ('generated', 'edited', 'final', 'pending', 'generating', 'error'):
        docs = [doc for doc in docs if str(getattr(doc, 'status', '')).lower() == status_filter]
    if university_filter:
        docs = [doc for doc in docs if university_filter in str(getattr(getattr(doc, 'university', None), 'name', '')).lower() or university_filter in str(getattr(getattr(getattr(doc, 'user', None), 'university', None), 'name', '')).lower()]
    if template_filter:
        docs = [doc for doc in docs if template_filter in str(getattr(getattr(doc, 'major', None), 'name', '')).lower() or template_filter in str(getattr(getattr(doc, 'degree', None), 'name', '')).lower()]

    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            docs = [doc for doc in docs if getattr(doc, 'createdAt', None) and doc.createdAt >= from_dt]
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            docs = [doc for doc in docs if getattr(doc, 'createdAt', None) and doc.createdAt <= to_dt]
        except ValueError:
            pass

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    items = [_serialize_report(r) for r in docs]
    if pagination_requested:
        return jsonify({'items': items, 'total': total, 'limit': limit, 'offset': offset})
    return jsonify(items)


@admin_bp.route('/reports/<report_id>', methods=['DELETE'])
@admin_required
def delete_report(current_user, report_id):
    Report.objects(id=report_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/work-keywords', methods=['GET'])
@admin_required
def get_work_keywords(current_user):
    import sys
    industry_type = str(request.args.get('industryType', '')).strip().lower()
    job_profile = str(request.args.get('jobProfile', '')).strip().lower()
    query = str(request.args.get('q', '')).strip().lower()
    major_id = str(request.args.get('major', '')).strip()
    is_active_raw = str(request.args.get('isActive', '')).strip().lower()
    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    limit = int(limit_raw) if str(limit_raw or '').strip().isdigit() else None
    offset = int(offset_raw) if str(offset_raw or '').strip().isdigit() else 0
    pagination_requested = limit is not None or offset_raw is not None or limit_raw is not None

    print(f"[DEBUG ADMIN /work-keywords] Incoming params: industry_type='{industry_type}', job_profile='{job_profile}', query='{query}', major_id='{major_id}'", file=sys.stderr)

    docs = list(WorkKeyword.objects().order_by('sortOrder', 'keyword'))
    print(f"[DEBUG ADMIN /work-keywords] Total before filters: {len(docs)}", file=sys.stderr)
    
    if industry_type:
        docs = [doc for doc in docs if industry_type in str(getattr(doc, 'industryType', '')).lower()]
        print(f"[DEBUG ADMIN /work-keywords] After industryType filter: {len(docs)}", file=sys.stderr)
    if job_profile:
        docs = [doc for doc in docs if job_profile in str(getattr(doc, 'jobProfile', '')).lower()]
        print(f"[DEBUG ADMIN /work-keywords] After jobProfile filter: {len(docs)}", file=sys.stderr)
    if query:
        docs = [doc for doc in docs if query in str(getattr(doc, 'keyword', '')).lower()]
        print(f"[DEBUG ADMIN /work-keywords] After query filter: {len(docs)}", file=sys.stderr)
    if major_id:
        docs = [
            doc for doc in docs
            if not getattr(doc, 'major', None) or str(_obj_id(getattr(doc, 'major', None))) == major_id
        ]
        print(f"[DEBUG ADMIN /work-keywords] After major filter: {len(docs)}", file=sys.stderr)
    
    if is_active_raw in ('true', '1', 'yes', 'on'):
        docs = [doc for doc in docs if bool(getattr(doc, 'isActive', True))]
        print(f"[DEBUG ADMIN /work-keywords] After isActive=true filter: {len(docs)}", file=sys.stderr)
    elif is_active_raw in ('false', '0', 'no', 'off'):
        docs = [doc for doc in docs if not bool(getattr(doc, 'isActive', True))]
        print(f"[DEBUG ADMIN /work-keywords] After isActive=false filter: {len(docs)}", file=sys.stderr)

    total = len(docs)
    if limit is not None:
        docs = docs[offset:offset + limit]
    elif pagination_requested and offset:
        docs = docs[offset:]

    items = [_serialize_work_keyword(doc) for doc in docs]
    if pagination_requested:
        return jsonify({'items': items, 'total': total, 'limit': limit, 'offset': offset})

    return jsonify(items)


@admin_bp.route('/work-keywords', methods=['POST'])
@admin_required
def create_work_keyword(current_user):
    data = request.get_json() or {}
    keyword = str(data.get('keyword', '')).strip()
    
    if not keyword:
        return jsonify({'message': 'Keyword is required'}), 400
    
    industry_type = str(data.get('industryType', '')).strip()
    job_profile = str(data.get('jobProfile', '')).strip()
    sort_order = int(data.get('sortOrder', 0) or 0)
    is_active = bool(data.get('isActive', True))
    
    # Resolve major if provided
    major_doc = None
    major_id = str(data.get('major', '')).strip()
    if major_id:
        major_doc = Major.objects(id=major_id).first()
        if not major_doc:
            return jsonify({'message': 'Invalid major'}), 400
    
    # Check for duplicates (same keyword, industry type, job profile, AND same major)
    existing = next(
        (doc for doc in WorkKeyword.objects()
         if _normalize_text(doc.keyword) == _normalize_text(keyword)
         and _normalize_text(getattr(doc, 'industryType', '')) == _normalize_text(industry_type)
         and _normalize_text(getattr(doc, 'jobProfile', '')) == _normalize_text(job_profile)
         and str(_obj_id(getattr(doc, 'major', None)) or '') == str(_obj_id(major_doc) or '')),
        None
    )
    if existing:
        return jsonify(_serialize_work_keyword(existing)), 200
    
    doc = WorkKeyword(
        keyword=keyword,
        industryType=industry_type,
        jobProfile=job_profile,
        major=major_doc,
        sortOrder=sort_order,
        isActive=is_active,
    )
    doc.save()
    return jsonify(_serialize_work_keyword(doc)), 201


@admin_bp.route('/work-keywords/<keyword_id>', methods=['GET'])
@admin_required
def get_work_keyword(current_user, keyword_id):
    doc = WorkKeyword.objects(id=keyword_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    return jsonify(_serialize_work_keyword(doc))


@admin_bp.route('/work-keywords/<keyword_id>', methods=['PUT'])
@admin_required
def update_work_keyword(current_user, keyword_id):
    doc = WorkKeyword.objects(id=keyword_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    
    data = request.get_json() or {}
    
    if 'keyword' in data:
        keyword = str(data.get('keyword', '')).strip()
        if not keyword:
            return jsonify({'message': 'Keyword cannot be empty'}), 400
        doc.keyword = keyword
    
    if 'industryType' in data:
        doc.industryType = str(data.get('industryType', '')).strip()
    
    if 'jobProfile' in data:
        doc.jobProfile = str(data.get('jobProfile', '')).strip()
    
    if 'major' in data:
        major_id = str(data.get('major', '')).strip()
        if major_id:
            major_doc = Major.objects(id=major_id).first()
            if not major_doc:
                return jsonify({'message': 'Invalid major'}), 400
            doc.major = major_doc
        else:
            # Empty string means universal keyword (no major restriction)
            doc.major = None
    
    if 'sortOrder' in data:
        doc.sortOrder = int(data.get('sortOrder', 0) or 0)
    
    if 'isActive' in data:
        doc.isActive = bool(data.get('isActive'))
    
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_work_keyword(doc))


@admin_bp.route('/work-keywords/<keyword_id>', methods=['DELETE'])
@admin_required
def delete_work_keyword(current_user, keyword_id):
    WorkKeyword.objects(id=keyword_id).delete()
    return jsonify({'message': 'Deleted'})




# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# BULK DELETE ROUTES (Multi-select operations)
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

@admin_bp.route('/degrees/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_degrees(current_user):
    """Delete multiple degrees and all majors/departments under each."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for degree_id in ids:
        doc = Degree.objects(id=degree_id).first()
        if doc:
            Major.objects(degree=degree_id).delete()
            Department.objects(degree=degree_id).delete()
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} degrees', 'deleted': deleted})


@admin_bp.route('/departments/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_departments(current_user):
    """Delete multiple departments."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for dept_id in ids:
        doc = Department.objects(id=dept_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} departments', 'deleted': deleted})


@admin_bp.route('/majors/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_majors(current_user):
    """Delete multiple majors."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for major_id in ids:
        doc = Major.objects(id=major_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} majors', 'deleted': deleted})


@admin_bp.route('/universities/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_universities(current_user):
    """Delete multiple universities."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for uni_id in ids:
        doc = University.objects(id=uni_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} universities', 'deleted': deleted})


@admin_bp.route('/colleges/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_colleges(current_user):
    """Delete multiple colleges."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for college_id in ids:
        doc = College.objects(id=college_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} colleges', 'deleted': deleted})


@admin_bp.route('/industries/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_industries(current_user):
    """Delete multiple industries."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for ind_id in ids:
        doc = Industry.objects(id=ind_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} industries', 'deleted': deleted})


@admin_bp.route('/work-keywords/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_work_keywords(current_user):
    """Delete multiple work keywords."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for kw_id in ids:
        doc = WorkKeyword.objects(id=kw_id).first()
        if doc:
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} work keywords', 'deleted': deleted})


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# CAREER OBJECTIVES (Resume Builder)
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

@admin_bp.route('/career-objectives', methods=['GET'])
@admin_required
def get_career_objectives(current_user):
    q = str(request.args.get('q', '')).strip()
    major_id = str(request.args.get('major', '')).strip()
    status_filter = str(request.args.get('status', '')).strip()
    limit = min(int(request.args.get('limit', 200) or 200), 500)
    offset = max(int(request.args.get('offset', 0) or 0), 0)
    
    docs = list(CareerObjective.objects().order_by('text'))
    if q:
        docs = [d for d in docs if q.lower() in str(d.text or '').lower()]
    if major_id:
        docs = [d for d in docs if 
            not getattr(d, 'major', None) or 
            str(_obj_id(d.major)) == major_id]
    if status_filter in ('approved', 'pending', 'rejected'):
        docs = [d for d in docs if d.approvalStatus == status_filter]

    total = len(docs)
    docs = docs[offset: offset + limit]
    return jsonify({
        'items': [_serialize_career_objective(d) for d in docs],
        'total': total,
        'limit': limit,
        'offset': offset,
    })


@admin_bp.route('/career-objectives', methods=['POST'])
@admin_required
def create_career_objective(current_user):
    data = request.get_json() or {}
    text = str(data.get('text', '')).strip()
    if not text:
        return jsonify({'message': 'text is required'}), 400
    
    major_doc = None
    if data.get('major'):
        major_doc = _resolve_reference_doc(Major, data.get('major'))
    
    doc = CareerObjective(
        text=text,
        major=major_doc,
        isActive=bool(data.get('isActive', True)),
        approvalStatus='approved',
        rejectionReason='',
        createdBy=current_user.id,
    )
    doc.save()
    return jsonify(_serialize_career_objective(doc)), 201


@admin_bp.route('/career-objectives/<obj_id>', methods=['PUT'])
@admin_required
def update_career_objective(current_user, obj_id):
    doc = CareerObjective.objects(id=obj_id).first()
    if not doc: return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    if 'text' in data: doc.text = str(data['text']).strip()
    if 'isActive' in data: doc.isActive = bool(data['isActive'])
    if 'major' in data:
        doc.major = _resolve_reference_doc(Major, data['major']) if data['major'] else None
    doc.approvalStatus = 'approved'
    doc.rejectionReason = ''
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_career_objective(doc))


@admin_bp.route('/career-objectives/<obj_id>', methods=['DELETE'])
@admin_required
def delete_career_objective(current_user, obj_id):
    CareerObjective.objects(id=obj_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/career-objectives/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_career_objectives(current_user):
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids: return jsonify({'message': 'No IDs provided'}), 400
    deleted = sum(1 for i in ids if CareerObjective.objects(id=i).delete())
    return jsonify({'message': f'Deleted {deleted}', 'deleted': deleted})


# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# RESUME KEYWORDS (Resume Builder)
# ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

@admin_bp.route('/resume-keywords', methods=['GET'])
@admin_required
def get_resume_keywords(current_user):
    category = str(request.args.get('category', '')).strip().lower()
    major_id = str(request.args.get('major', '')).strip()
    industry_type = str(request.args.get('industryType', '')).strip().lower()
    q = str(request.args.get('q', '')).strip().lower()
    limit_raw = request.args.get('limit')
    limit = min(int(limit_raw) if str(limit_raw or '').strip().isdigit() else 200, 500)
    offset = max(int(request.args.get('offset', 0) or 0), 0)
    pagination_requested = limit_raw is not None or request.args.get('offset') is not None
    
    docs = list(ResumeKeyword.objects().order_by('sortOrder', 'keyword'))
    if category:
        docs = [d for d in docs if d.category == category]
    if major_id:
        docs = [d for d in docs if 
            not getattr(d, 'major', None) or 
            str(_obj_id(d.major)) == major_id]
    if industry_type:
        docs = [d for d in docs if 
            industry_type in str(d.industryType or '').lower()]
    if q:
        docs = [d for d in docs if q in str(d.keyword or '').lower()]

    total = len(docs)
    docs = docs[offset: offset + limit]
    payload = {
        'items': [_serialize_resume_keyword(d) for d in docs],
        'total': total,
        'limit': limit,
        'offset': offset,
    }
    if pagination_requested:
        return jsonify(payload)
    return jsonify(payload['items'])


@admin_bp.route('/resume-keywords', methods=['POST'])
@admin_required
def create_resume_keyword(current_user):
    data = request.get_json() or {}
    keyword = str(data.get('keyword', '')).strip()
    category = str(data.get('category', '')).strip()
    if not keyword or not category:
        return jsonify({'message': 'keyword and category are required'}), 400
    valid_cats = ('experience', 'project', 'volunteering', 'skill', 'technical')
    if category not in valid_cats:
        return jsonify({'message': f'category must be one of: {valid_cats}'}), 400
    
    major_doc = None
    if data.get('major'):
        major_doc = _resolve_reference_doc(Major, data.get('major'))
    
    doc = ResumeKeyword(
        keyword=keyword,
        category=category,
        major=major_doc,
        industryType=str(data.get('industryType', '')).strip(),
        jobProfile=str(data.get('jobProfile', '')).strip(),
        sortOrder=int(data.get('sortOrder', 0) or 0),
        isActive=bool(data.get('isActive', True)),
        createdBy=current_user.id,
    )
    doc.save()
    return jsonify(_serialize_resume_keyword(doc)), 201


@admin_bp.route('/resume-keywords/<kw_id>', methods=['PUT'])
@admin_required
def update_resume_keyword(current_user, kw_id):
    doc = ResumeKeyword.objects(id=kw_id).first()
    if not doc: return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    for field in ['keyword', 'category', 'industryType', 'jobProfile', 'sortOrder', 'isActive']:
        if field in data: setattr(doc, field, data[field])
    if 'major' in data:
        doc.major = _resolve_reference_doc(Major, data['major']) if data['major'] else None
    doc.updatedAt = datetime.utcnow()
    doc.save()
    return jsonify(_serialize_resume_keyword(doc))


@admin_bp.route('/resume-keywords/<kw_id>', methods=['DELETE'])
@admin_required
def delete_resume_keyword(current_user, kw_id):
    ResumeKeyword.objects(id=kw_id).delete()
    return jsonify({'message': 'Deleted'})


# ── RESUME TRACKING ───────────────────────────────────────────────────────

@admin_bp.route('/resumes', methods=['GET'])
@admin_required
def admin_get_resumes(current_user):
    q = str(request.args.get('q', '') or '').strip().lower()
    status_filter = str(request.args.get('status', '') or '').strip().lower()
    from_raw = str(request.args.get('from', '') or '').strip()
    to_raw = str(request.args.get('to', '') or '').strip()

    limit_raw = request.args.get('limit')
    offset_raw = request.args.get('offset')
    try:
        limit = min(int(limit_raw) if str(limit_raw or '').strip().isdigit() else 50, 200)
    except Exception:
        limit = 50
    try:
        offset = max(int(offset_raw) if str(offset_raw or '').strip().lstrip('-').isdigit() else 0, 0)
    except Exception:
        offset = 0

    from_dt = None
    to_dt = None
    try:
        if from_raw:
            from_dt = datetime.strptime(from_raw, '%Y-%m-%d').date()
    except Exception:
        from_dt = None
    try:
        if to_raw:
            to_dt = datetime.strptime(to_raw, '%Y-%m-%d').date()
    except Exception:
        to_dt = None

    docs = list(Resume.objects())
    docs.sort(key=lambda d: getattr(d, 'updatedAt', datetime.min), reverse=True)

    if q:
        def _matches_search(doc):
            user_obj = getattr(doc, 'user', None)
            haystack = ' '.join([
                str(getattr(doc, 'title', '') or ''),
                str(getattr(doc, 'fullName', '') or ''),
                str(getattr(doc, 'email', '') or ''),
                str(getattr(user_obj, 'name', '') or ''),
                str(getattr(user_obj, 'email', '') or ''),
            ]).lower()
            return q in haystack
        docs = [d for d in docs if _matches_search(d)]

    if status_filter:
        docs = [d for d in docs if str(getattr(d, 'status', 'draft') or 'draft').lower() == status_filter]

    if from_dt or to_dt:
        filtered = []
        for doc in docs:
            updated_at = getattr(doc, 'updatedAt', None) or getattr(doc, 'createdAt', None)
            if not updated_at:
                continue
            updated_date = updated_at.date() if hasattr(updated_at, 'date') else None
            if not updated_date:
                continue
            if from_dt and updated_date < from_dt:
                continue
            if to_dt and updated_date > to_dt:
                continue
            filtered.append(doc)
        docs = filtered

    total = len(docs)
    page = docs[offset: offset + limit]

    return jsonify({
        'items': [_serialize_resume(doc) for doc in page],
        'total': total,
        'limit': limit,
        'offset': offset,
    }), 200


@admin_bp.route('/resumes/stats', methods=['GET'])
@admin_required
def admin_resume_stats(current_user):
    docs = list(Resume.objects())
    stats = {
        'total': len(docs),
        'draft': 0,
        'generating': 0,
        'generated': 0,
        'downloaded': 0,
    }
    total_downloads = 0

    for doc in docs:
        status = str(getattr(doc, 'status', 'draft') or 'draft').lower()
        if status not in stats:
            stats[status] = 0
        stats[status] += 1
        total_downloads += int(getattr(doc, 'downloadCount', 0) or 0)

    stats['totalDownloads'] = total_downloads
    return jsonify(stats), 200


@admin_bp.route('/resumes/<resume_id>', methods=['GET'])
@admin_required
def admin_get_resume(current_user, resume_id):
    doc = Resume.objects(id=resume_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    return jsonify(_serialize_resume(doc, include_full=True)), 200


@admin_bp.route('/resumes/<resume_id>/pdf', methods=['GET'])
@admin_required
def admin_resume_pdf(current_user, resume_id):
    from utils.pdf import generate_pdf_from_html
    from routes.student import _serialize_resume_full, _serialize_profile

    doc = Resume.objects(id=resume_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404

    preview_mode = str(request.args.get('preview', '')).lower() in {'1', 'true', 'yes'}
    html_string = render_template(
        'resume_pdf_template.html',
        resume=_serialize_resume_full(doc),
        profile=_serialize_profile(current_user),
        user=_serialize_profile(current_user),
    )
    base_url = request.host_url.rstrip('/')
    if '<head>' in html_string:
        html_string = html_string.replace('<head>', f'<head><base href="{base_url}/">', 1)

    pdf_bytes = generate_pdf_from_html(
        html_string,
        base_url=base_url,
        student_name=current_user.name if getattr(current_user, 'name', None) else 'Student',
    )

    filename = f'resume_{_obj_id(doc) or resume_id}.pdf'
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=not preview_mode,
        download_name=filename if not preview_mode else 'preview.pdf',
    )


@admin_bp.route('/resumes/<resume_id>', methods=['DELETE'])
@admin_required
def admin_delete_resume(current_user, resume_id):
    doc = Resume.objects(id=resume_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    try:
        doc.delete()
    except Exception:
        pass
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/resumes/bulk-delete', methods=['POST'])
@admin_required
def admin_bulk_delete_resumes(current_user):
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400

    deleted = 0
    for resume_id in ids:
        doc = Resume.objects(id=resume_id).first()
        if not doc:
            continue
        try:
            doc.delete()
            deleted += 1
        except Exception:
            continue

    return jsonify({'message': f'Deleted {deleted} resumes', 'deleted': deleted})


@admin_bp.route('/resume-keywords/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_resume_keywords(current_user):
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids: return jsonify({'message': 'No IDs provided'}), 400
    deleted = 0
    for i in ids:
        if ResumeKeyword.objects(id=i).delete(): deleted += 1
    return jsonify({'message': f'Deleted {deleted}', 'deleted': deleted})


@admin_bp.route('/users/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_users(current_user):
    """Delete multiple users and all reports + image folders under each."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for user_id in ids:
        user = User.objects(id=user_id).first()
        if user:
            # Delete all reports belonging to this user
            user_reports = Report.objects(user=user_id)
            for r in user_reports:
                # Clean up report image folder
                report_images_dir = os.path.join('static', 'uploads', 'report_images', str(r.id))
                shutil.rmtree(report_images_dir, ignore_errors=True)
            
            # Delete all reports and payments
            user_reports.delete()
            Payment.objects(user=user_id).delete()
            
            # Delete the user
            user.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} users', 'deleted': deleted})


@admin_bp.route('/reports/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_reports(current_user):
    """Delete multiple reports and their image folders."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    
    deleted = 0
    for report_id in ids:
        doc = Report.objects(id=report_id).first()
        if doc:
            # Clean up report image folder
            report_images_dir = os.path.join('static', 'uploads', 'report_images', str(report_id))
            shutil.rmtree(report_images_dir, ignore_errors=True)
            
            # Delete the report
            doc.delete()
            deleted += 1
    
    return jsonify({'message': f'Deleted {deleted} reports', 'deleted': deleted})


@admin_bp.route('/project-titles/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_project_titles(current_user):
    """Delete multiple project titles."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400

    deleted = 0
    for title_id in ids:
        doc = ProjectTitle.objects(id=title_id).first()
        if doc:
            doc.delete()
            deleted += 1

    return jsonify({'message': f'Deleted {deleted} project titles', 'deleted': deleted})


# Register report sections routes
from routes.admin_report_sections import register_routes
register_routes(admin_bp)


# === BLOG POST ROUTES ===

def _slugify(text):
    """Convert text to URL-safe slug."""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def _serialize_blog_post(doc):
    """Serialize a BlogPost document for API response."""
    return {
        '_id': _obj_id(doc),
        'title': getattr(doc, 'title', ''),
        'slug': getattr(doc, 'slug', ''),
        'excerpt': getattr(doc, 'excerpt', ''),
        'content': getattr(doc, 'content', ''),
        'coverImage': getattr(doc, 'coverImage', ''),
        'tags': list(getattr(doc, 'tags', []) or []),
        'author': getattr(doc, 'author', 'ReportGen Team'),
        'isPublished': bool(getattr(doc, 'isPublished', False)),
        'publishedAt': doc.publishedAt.isoformat() if getattr(doc, 'publishedAt', None) else None,
        'createdAt': doc.createdAt.isoformat() if getattr(doc, 'createdAt', None) else None,
        'updatedAt': doc.updatedAt.isoformat() if getattr(doc, 'updatedAt', None) else None,
    }


@admin_bp.route('/blog', methods=['GET'])
@admin_required
def get_blog_posts(current_user):
    """Get all blog posts, optionally filtered by search query."""
    q = str(request.args.get('q', '') or '').strip().lower()
    docs = list(BlogPost.objects().order_by('-createdAt'))
    if q:
        docs = [d for d in docs if q in str(d.title or '').lower()
                or q in str(d.excerpt or '').lower()]
    return jsonify([_serialize_blog_post(d) for d in docs])


@admin_bp.route('/blog', methods=['POST'])
@admin_required
def create_blog_post(current_user):
    """Create a new blog post."""
    data = request.get_json() or {}
    title = str(data.get('title') or '').strip()
    if not title:
        return jsonify({'message': 'title is required'}), 400

    slug = str(data.get('slug') or '').strip() or _slugify(title)

    # Ensure slug is unique
    base_slug = slug
    counter = 1
    while BlogPost.objects(slug=slug).first():
        slug = f'{base_slug}-{counter}'
        counter += 1

    doc = BlogPost(
        title=title,
        slug=slug,
        excerpt=str(data.get('excerpt') or '').strip(),
        content=str(data.get('content') or '').strip(),
        coverImage=str(data.get('coverImage') or '').strip(),
        tags=[str(t).strip() for t in (data.get('tags') or []) if str(t).strip()],
        author=str(data.get('author') or 'ReportGen Team').strip(),
        isPublished=bool(data.get('isPublished', False)),
    )
    if doc.isPublished:
        doc.publishedAt = dt.datetime.utcnow()
    doc.save()
    return jsonify(_serialize_blog_post(doc)), 201


@admin_bp.route('/blog/<post_id>', methods=['PUT'])
@admin_required
def update_blog_post(current_user, post_id):
    """Update a blog post."""
    doc = BlogPost.objects(id=post_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}

    if 'title' in data:
        doc.title = str(data['title']).strip()
    if 'slug' in data and data['slug']:
        doc.slug = str(data['slug']).strip()
    if 'excerpt' in data:
        doc.excerpt = str(data['excerpt']).strip()
    if 'content' in data:
        doc.content = str(data['content']).strip()
    if 'coverImage' in data:
        doc.coverImage = str(data['coverImage']).strip()
    if 'tags' in data:
        doc.tags = [str(t).strip() for t in (data['tags'] or []) if str(t).strip()]
    if 'author' in data:
        doc.author = str(data['author']).strip() or 'ReportGen Team'
    if 'isPublished' in data:
        was_published = bool(getattr(doc, 'isPublished', False))
        doc.isPublished = bool(data['isPublished'])
        if doc.isPublished and not was_published:
            doc.publishedAt = dt.datetime.utcnow()

    doc.save()
    return jsonify(_serialize_blog_post(doc))


@admin_bp.route('/blog/<post_id>', methods=['DELETE'])
@admin_required
def delete_blog_post(current_user, post_id):
    """Delete a blog post."""
    doc = BlogPost.objects(id=post_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    doc.delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/blog/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_blog_posts(current_user):
    """Delete multiple blog posts."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    deleted = 0
    for i in ids:
        doc = BlogPost.objects(id=i).first()
        if doc:
            doc.delete()
            deleted += 1
    return jsonify({'message': f'Deleted {deleted}', 'deleted': deleted})


# === FAQ ITEM ROUTES ===

def _serialize_faq(doc):
    """Serialize a FaqItem document for API response."""
    return {
        '_id': _obj_id(doc),
        'question': getattr(doc, 'question', ''),
        'answer': getattr(doc, 'answer', ''),
        'category': getattr(doc, 'category', 'General'),
        'sortOrder': getattr(doc, 'sortOrder', 0),
        'isActive': bool(getattr(doc, 'isActive', True)),
        'createdAt': doc.createdAt.isoformat() if getattr(doc, 'createdAt', None) else None,
    }


@admin_bp.route('/faq', methods=['GET'])
@admin_required
def get_faq_items(current_user):
    """Get all FAQ items, sorted by category and sort order."""
    docs = list(FaqItem.objects().order_by('category', 'sortOrder', 'question'))
    return jsonify([_serialize_faq(d) for d in docs])


@admin_bp.route('/faq', methods=['POST'])
@admin_required
def create_faq_item(current_user):
    """Create a new FAQ item."""
    data = request.get_json() or {}
    question = str(data.get('question') or '').strip()
    answer = str(data.get('answer') or '').strip()
    if not question or not answer:
        return jsonify({'message': 'question and answer are required'}), 400
    doc = FaqItem(
        question=question,
        answer=answer,
        category=str(data.get('category') or 'General').strip(),
        sortOrder=int(data.get('sortOrder') or 0),
        isActive=bool(data.get('isActive', True)),
    )
    doc.save()
    return jsonify(_serialize_faq(doc)), 201


@admin_bp.route('/faq/<item_id>', methods=['PUT'])
@admin_required
def update_faq_item(current_user, item_id):
    """Update a FAQ item."""
    doc = FaqItem.objects(id=item_id).first()
    if not doc:
        return jsonify({'message': 'Not found'}), 404
    data = request.get_json() or {}
    for field in ['question', 'answer', 'category']:
        if field in data:
            setattr(doc, field, str(data[field]).strip())
    if 'sortOrder' in data:
        doc.sortOrder = int(data['sortOrder'] or 0)
    if 'isActive' in data:
        doc.isActive = bool(data['isActive'])
    doc.updatedAt = dt.datetime.utcnow()
    doc.save()
    return jsonify(_serialize_faq(doc))


@admin_bp.route('/faq/<item_id>', methods=['DELETE'])
@admin_required
def delete_faq_item(current_user, item_id):
    """Delete a FAQ item."""
    FaqItem.objects(id=item_id).delete()
    return jsonify({'message': 'Deleted'})


@admin_bp.route('/faq/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_faq_items(current_user):
    """Delete multiple FAQ items."""
    data = request.get_json() or {}
    ids = [str(i).strip() for i in (data.get('ids') or []) if str(i).strip()]
    if not ids:
        return jsonify({'message': 'No IDs provided'}), 400
    deleted = 0
    for i in ids:
        doc = FaqItem.objects(id=i).first()
        if doc:
            doc.delete()
            deleted += 1
    return jsonify({'message': f'Deleted {deleted}', 'deleted': deleted})

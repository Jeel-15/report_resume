from flask import request, jsonify
from functools import wraps
from datetime import datetime
from models.university import University
from models.report_section_template import UniversityReportTemplate, ReportSectionItem
from routes.auth import token_required

# ============================================================================
# HIERARCHICAL REPORT SECTIONS MANAGEMENT ENDPOINTS
# 3-Level Cascade: University → College → Major (like Skillinc grading)
# ============================================================================

def _obj_id(doc):
    """Helper: convert document to ID string"""
    if not doc:
        return None
    direct_id = getattr(doc, 'id', None)
    if direct_id is not None:
        return str(direct_id)
    raw_data = getattr(doc, '_data', None) or {}
    raw_id = raw_data.get('id')
    return str(raw_id) if raw_id is not None else None


def admin_required(f):
    """Decorator: require admin role"""
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin privilege required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated


def _serialize_report_section_item(item):
    """Serialize a ReportSectionItem embedded document"""
    if not item:
        return None
    return {
        'key': getattr(item, 'key', ''),
        'title': getattr(item, 'title', ''),
        'description': getattr(item, 'description', ''),
        'sortOrder': str(getattr(item, 'sortOrder', '0')),
    }

def _serialize_university_report_template(doc):
    """Serialize UniversityReportTemplate document"""
    sections = [_serialize_report_section_item(s) for s in (doc.sections or [])]
    source = 'university_default' if sections else 'none'
    return {
        '_id': _obj_id(doc),
        'university': {
            '_id': _obj_id(doc.university),
            'name': doc.university.name if doc.university else None,
        } if doc.university else None,
        'sections': sections,
        'source': source,
        'inheritanceLevel': 'university',
        'description': doc.description,
        'isActive': doc.isActive,
        'isDefault': bool(getattr(doc, 'isDefault', False)),
        'createdBy': {
            '_id': _obj_id(doc.createdBy),
            'name': getattr(doc.createdBy, 'name', None),
        } if getattr(doc, 'createdBy', None) else None,
        'createdAt': doc.createdAt.isoformat() if getattr(doc, 'createdAt', None) else None,
        'updatedAt': doc.updatedAt.isoformat() if getattr(doc, 'updatedAt', None) else None,
    }

# ===== UNIVERSITY REPORT TEMPLATES =====

def register_routes(admin_bp):
    """Register report sections routes to the admin blueprint"""

    @admin_bp.route('/university-report-templates/<university_id>', methods=['GET'])
    @admin_required
    def get_university_report_template(current_user, university_id):
        """Get report section template for a university (or create default)"""
        doc = UniversityReportTemplate.objects(university=university_id).first()
        if not doc:
            # Auto-create default template
            university = University.objects(id=university_id).first()
            if not university:
                return jsonify({'message': 'University not found'}), 404
            
            doc = UniversityReportTemplate(
                university=university,
                sections=[
                    ReportSectionItem(key='introduction', title='Introduction', description='Project introduction and background'),
                    ReportSectionItem(key='objectives', title='Objectives', description='Goals and objectives of the project'),
                    ReportSectionItem(key='methodology', title='Methodology', description='Approach and methods used'),
                    ReportSectionItem(key='results', title='Results', description='Key findings and results'),
                    ReportSectionItem(key='conclusion', title='Conclusion', description='Conclusion and recommendations'),
                ],
                description=f'Default report structure for {university.name}',
                isActive=True,
                createdBy=current_user.id,
            )
            doc.save()
        
        return jsonify(_serialize_university_report_template(doc))


    @admin_bp.route('/university-report-templates/<university_id>', methods=['PUT'])
    @admin_required
    def update_university_report_template(current_user, university_id):
        """Update report section template for a university"""
        doc = UniversityReportTemplate.objects(university=university_id).first()
        if not doc:
            university = University.objects(id=university_id).first()
            if not university:
                return jsonify({'message': 'University not found'}), 404
            
            doc = UniversityReportTemplate(
                university=university,
                createdBy=current_user.id,
            )
        
        data = request.get_json() or {}
        
        if 'sections' in data:
            raw_sections = data.get('sections') or []
            sections = []
            for idx, raw in enumerate(raw_sections):
                if not isinstance(raw, dict):
                    return jsonify({'message': f'sections[{idx}] must be an object'}), 400
                
                key = str(raw.get('key', '')).strip()
                title = str(raw.get('title', '')).strip()
                description = str(raw.get('description', ''))
                sort_order = str(raw.get('sortOrder', str(idx)))
                
                if not key or not title:
                    return jsonify({'message': f'sections[{idx}] requires key and title'}), 400
                
                sections.append(ReportSectionItem(key=key, title=title, description=description, sortOrder=sort_order))
            
            doc.sections = sections
        
        if 'description' in data:
            doc.description = str(data.get('description', '')).strip()
        
        if 'isActive' in data:
            doc.isActive = bool(data.get('isActive'))
        
        doc.updatedAt = datetime.utcnow()
        doc.save()
        return jsonify(_serialize_university_report_template(doc))


    @admin_bp.route('/default-report-template', methods=['GET'])
    @admin_required
    def get_default_report_template(current_user):
        """Get the system-wide default report section template (isDefault=True)."""
        # Find existing default
        doc = None
        try:
            for candidate in UniversityReportTemplate.objects():
                if bool(getattr(candidate, 'isDefault', False)):
                    doc = candidate
                    break
        except Exception:
            pass

        if not doc:
            # Auto-create the system default template with sensible starter sections
            doc = UniversityReportTemplate(
                university=None,
                isDefault=True,
                isActive=True,
                description='System-wide default report sections. Used when a university has no custom template configured.',
                sections=[
                    ReportSectionItem(key='acknowledgement',  title='Acknowledgement',              description='Thanks to mentors, institution, and supporters.',           sortOrder=0),
                    ReportSectionItem(key='abstract',         title='Abstract',                     description='Summary of internship, activities, and outcomes.',          sortOrder=1),
                    ReportSectionItem(key='introduction',     title='Introduction',                 description='Background, objectives, and scope of internship.',          sortOrder=2),
                    ReportSectionItem(key='workDescription',  title='Work Description & Activities',description='Detailed tasks, tools, process, and execution.',           sortOrder=3),
                    ReportSectionItem(key='learningOutcomes', title='Learning Outcomes',            description='Skills, knowledge, and competencies gained.',               sortOrder=4),
                    ReportSectionItem(key='conclusion',       title='Conclusion & Recommendations', description='Summary, reflections, and recommendations.',               sortOrder=5),
                    ReportSectionItem(key='references',       title='References',                   description='Books, websites, papers, and other sources used.',         sortOrder=6),
                ],
                createdBy=current_user.id,
            )
            doc.save()

        return jsonify(_serialize_university_report_template(doc))


    @admin_bp.route('/default-report-template', methods=['PUT'])
    @admin_required
    def update_default_report_template(current_user):
        """Update the system-wide default report section template."""
        # Find existing
        doc = None
        try:
            for candidate in UniversityReportTemplate.objects():
                if bool(getattr(candidate, 'isDefault', False)):
                    doc = candidate
                    break
        except Exception:
            pass

        if not doc:
            doc = UniversityReportTemplate(
                university=None,
                isDefault=True,
                createdBy=current_user.id,
            )

        data = request.get_json() or {}

        if 'sections' in data:
            raw_sections = data.get('sections') or []
            sections = []
            for idx, raw in enumerate(raw_sections):
                if not isinstance(raw, dict):
                    return jsonify({'message': f'sections[{idx}] must be an object'}), 400
                key = str(raw.get('key', '')).strip()
                title = str(raw.get('title', '')).strip()
                description = str(raw.get('description', ''))
                sort_order = str(raw.get('sortOrder', str(idx)))
                if not key or not title:
                    return jsonify({'message': f'sections[{idx}] requires key and title'}), 400
                sections.append(ReportSectionItem(key=key, title=title, description=description, sortOrder=sort_order))
            doc.sections = sections

        if 'description' in data:
            doc.description = str(data.get('description', '')).strip()

        if 'isActive' in data:
            doc.isActive = bool(data.get('isActive'))

        doc.updatedAt = datetime.utcnow()
        doc.save()
        return jsonify(_serialize_university_report_template(doc))


from models.major import Major
from models.college import College
from models.university import University
from models.report_section_template import UniversityReportTemplate


def serialize_report_section_item(item):
    if not item:
        return None
    return {
        'key': getattr(item, 'key', ''),
        'title': getattr(item, 'title', ''),
        'description': getattr(item, 'description', ''),
        'sortOrder': str(getattr(item, 'sortOrder', '0')),
    }


def _normalize_items(items):
    return [
        serialize_report_section_item(item)
        for item in (items or [])
        if getattr(item, 'key', '') and getattr(item, 'title', '')
    ]


def _resolve_doc(value, model):
    if not value:
        return None
    if isinstance(value, model):
        return value
    return model.objects(id=str(value)).first()


def get_system_default_template():
    """Fetch the one system-wide default UniversityReportTemplate (isDefault=True)."""
    try:
        # Fetch all and filter in Python — SQLite backend BooleanField filter is unreliable
        for doc in UniversityReportTemplate.objects():
            if bool(getattr(doc, 'isDefault', False)):
                return doc
    except Exception:
        pass
    return None


def resolve_effective_report_sections(major=None, college=None, university=None, include_legacy=True):
    """
    Resolve report sections using this priority:
    1. University-specific template (UniversityReportTemplate where university matches)
    2. Legacy fallback: major.reportSections (backward compat)
    3. System default template (UniversityReportTemplate where isDefault=True)
    4. Empty list (no sections configured anywhere)
    """
    major_doc = _resolve_doc(major, Major)
    college_doc = _resolve_doc(college, College)
    university_doc = _resolve_doc(university, University)

    # Resolve university_doc from various sources
    if not university_doc and college_doc:
        university_doc = getattr(college_doc, 'university', None)

    if not university_doc and major_doc and getattr(major_doc, 'degree', None):
        university_doc = _resolve_doc(getattr(major_doc.degree, 'university', None), University)

    # Priority 1: University-specific template
    if university_doc:
        try:
            university_template = UniversityReportTemplate.objects(university=university_doc.id).first()
        except Exception:
            university_template = None
        if university_template and university_template.sections:
            return {
                'sections': _normalize_items(university_template.sections),
                'source': 'university_default',
                'inheritanceLevel': 'university',
                'major': major_doc,
                'college': college_doc,
                'university': university_doc,
            }

    # Priority 2: Legacy fallback — major.reportSections
    if include_legacy and major_doc and getattr(major_doc, 'reportSections', None):
        return {
            'sections': _normalize_items(major_doc.reportSections),
            'source': 'major_legacy',
            'inheritanceLevel': 'major',
            'major': major_doc,
            'college': college_doc,
            'university': university_doc,
        }

    # Priority 3: System default template (admin-defined global fallback)
    system_default = get_system_default_template()
    if system_default and system_default.sections:
        return {
            'sections': _normalize_items(system_default.sections),
            'source': 'system_default',
            'inheritanceLevel': 'system',
            'major': major_doc,
            'college': college_doc,
            'university': university_doc,
        }

    # Priority 4: Nothing found
    return {
        'sections': [],
        'source': 'none',
        'inheritanceLevel': 'none',
        'major': major_doc,
        'college': college_doc,
        'university': university_doc,
    }
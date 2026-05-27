"""
AssignmentSession — stores one student assignment workspace.

SQLite adapter notes (mongoengine.py custom adapter):
- DictField stored as JSON string — access as plain dict
- ListField(DictField()) stored as JSON array string
- BooleanField stored as INTEGER 0/1 — filter in Python, not in query kwargs
- ReferenceField('User') stored as INTEGER FK — use multi-strategy matching
"""
from mongoengine import (
    Document, StringField, BooleanField, DateTimeField,
    ReferenceField, ListField, DictField, IntField
)
import datetime


class AssignmentSession(Document):
    meta = {'collection': 'assignment_sessions', 'strict': False}

    # Owner
    user = ReferenceField('User', required=True)

    # Identity
    title = StringField(default='Untitled Assignment')
    assignmentType = StringField(
        required=True,
        choices=(
            'essay', 'research_paper', 'lab_report',
            'case_study', 'presentation_script',
        )
    )

    # Context snapshot from student profile at session creation time
    # Snapshot prevents profile changes from altering existing sessions
    universityName = StringField(default='')
    degreeName     = StringField(default='')
    majorName      = StringField(default='')

    # Assignment-type-specific inputs
    # All types stored in one flexible dict to avoid schema migration
    # See PRD Section 5 for per-type field definitions
    contextInputs = DictField(default=dict)

    # Generated document — list of section dicts
    # Each section: {section_key, title, content_markdown, sort_order}
    documentSections = ListField(DictField(), default=list)

    # Full document assembled from sections (for word count + DOCX/PDF)
    fullContentMarkdown = StringField(default='')

    # Chat refinement history
    # Each entry: {role: 'user'|'assistant', message, timestamp}
    chatHistory = ListField(DictField(), default=list)

    # Generation lifecycle
    status = StringField(
        choices=('draft', 'generating', 'generated', 'error'),
        default='draft'
    )
    errorMessage = StringField(default='')

    # Metrics
    wordCountCurrent  = IntField(default=0)
    wordCountTarget   = IntField(default=0)
    generationCount   = IntField(default=0)
    apiTokensConsumed = IntField(default=0)

    # Soft delete — filter in Python: [s for s in all if not s.isDeleted]
    isDeleted = BooleanField(default=False)

    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField, ListField, IntField, EmbeddedDocument, EmbeddedDocumentListField
import datetime

class ReportSectionItem(EmbeddedDocument):
    """Individual report section with title and description"""
    meta = {'strict': False}
    
    key = StringField(required=True)
    title = StringField(required=True)
    description = StringField(default='')
    sortOrder = IntField(default=0)

class UniversityReportTemplate(Document):
    """Default report sections template for an entire university"""
    meta = {
        'collection': 'university_report_templates',
        'strict': False,
        'indexes': []
    }
    
    # university is optional so we can have a system-wide default record with university=None
    university = ReferenceField('University', required=False, default=None)
    sections = EmbeddedDocumentListField(ReportSectionItem, default=list)
    description = StringField(default='Default report structure for this university')
    isActive = BooleanField(default=True)
    isDefault = BooleanField(default=False)
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

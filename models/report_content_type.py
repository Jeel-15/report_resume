from mongoengine import Document, StringField, BooleanField, DateTimeField, IntField, ReferenceField
import datetime


class ReportContentType(Document):
    meta = {'collection': 'report_content_types', 'strict': False}

    name = StringField(required=True)
    sortOrder = IntField(default=0)
    isActive = BooleanField(default=True)
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)
from mongoengine import Document, StringField, DateTimeField, DictField, ReferenceField
import datetime

class AuditLog(Document):
    meta = {'collection': 'audit_logs', 'strict': False}

    adminUser = ReferenceField('User', required=True)
    action = StringField(required=True)
    targetType = StringField(default='')
    targetId = StringField(default='')
    details = DictField(default=dict)
    ipAddress = StringField(default='')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)

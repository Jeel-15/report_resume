import datetime
from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField


class Department(Document):
    meta = {
        'collection': 'departments',
        'strict': False,
    }

    name = StringField(required=True)
    degree = ReferenceField('Degree', required=True)
    approvalStatus = StringField(
        choices=('approved', 'pending', 'rejected'),
        default='approved',
    )
    rejectionReason = StringField(default='')
    createdBy = ReferenceField('User')
    isActive = BooleanField(default=True)
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

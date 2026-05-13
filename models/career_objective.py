from mongoengine import (
    Document, StringField, BooleanField, DateTimeField, ReferenceField
)
import datetime


class CareerObjective(Document):
    meta = {'collection': 'career_objectives', 'strict': False}

    text = StringField(required=True)
    major = ReferenceField('Major', default=None)
    isActive = BooleanField(default=True)
    approvalStatus = StringField(
        choices=('approved', 'pending', 'rejected'),
        default='approved'
    )
    rejectionReason = StringField(default='')
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

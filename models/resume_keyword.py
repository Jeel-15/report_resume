from mongoengine import (
    Document, StringField, BooleanField, DateTimeField,
    ReferenceField, IntField
)
import datetime


class ResumeKeyword(Document):
    meta = {'collection': 'resume_keywords', 'strict': False}

    keyword = StringField(required=True)
    category = StringField(
        choices=('experience', 'project', 'volunteering', 'skill', 'technical'),
        required=True
    )

    major = ReferenceField('Major', default=None)
    industryType = StringField(default='')
    jobProfile = StringField(default='')

    sortOrder = IntField(default=0)
    isActive = BooleanField(default=True)
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

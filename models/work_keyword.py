import datetime
from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField, IntField


class WorkKeyword(Document):
    meta = {
        'collection': 'work_keywords',
        'strict': False,
    }

    keyword = StringField(required=True)
    industryType = StringField(default='')
    jobProfile = StringField(default='')
    major = ReferenceField('Major', default=None)  # Optional: None = universal keyword, shown to all majors
    sortOrder = IntField(default=0)
    isActive = BooleanField(default=True)
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

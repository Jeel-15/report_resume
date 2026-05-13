from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField
import datetime


class ProjectTitle(Document):
    meta = {'collection': 'project_titles', 'strict': False}

    title = StringField(required=True)
    major = ReferenceField('Major', required=True)
    degree = ReferenceField('Degree')           # denormalized for easy filtering
    isActive = BooleanField(default=True)
    createdBy = ReferenceField('User')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)
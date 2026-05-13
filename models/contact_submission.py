from mongoengine import Document, StringField, DateTimeField
import datetime


class ContactSubmission(Document):
    meta = {'collection': 'contact_submissions', 'strict': False}

    name = StringField(required=True)
    email = StringField(required=True)
    subject = StringField(required=True)
    subjectKey = StringField(default='')
    message = StringField(required=True)
    status = StringField(default='new')
    source = StringField(default='contact-page')
    ipAddress = StringField(default='')
    userAgent = StringField(default='')
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
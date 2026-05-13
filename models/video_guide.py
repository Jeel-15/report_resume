from mongoengine import Document, StringField, BooleanField, DateTimeField, IntField
import datetime

class VideoGuide(Document):
    meta = {'collection': 'video_guides', 'strict': False}

    title = StringField(required=True)
    description = StringField(default='')
    videoUrl = StringField(required=True)
    videoType = StringField(choices=('youtube', 'upload'), default='youtube')
    sortOrder = IntField(default=0)
    isActive = BooleanField(default=True)
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

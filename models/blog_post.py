from mongoengine import (
    Document, StringField, BooleanField,
    DateTimeField, ListField
)
import datetime


class BlogPost(Document):
    meta = {'collection': 'blog_posts', 'strict': False}

    title       = StringField(required=True)
    slug        = StringField(required=True, unique=True)
    # Short description shown on blog listing page
    excerpt     = StringField(default='')
    # Full HTML content of the post
    content     = StringField(default='')
    # Cover image URL (uploaded or external)
    coverImage  = StringField(default='')
    # Tags like ['AI', 'Resume', 'Internship']
    tags        = ListField(StringField(), default=list)
    # Author name (plain string, no user reference needed)
    author      = StringField(default='ReportGen Team')
    isPublished = BooleanField(default=False)
    publishedAt = DateTimeField(default=None)
    createdAt   = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt   = DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updatedAt = datetime.datetime.utcnow()
        if self.isPublished and not self.publishedAt:
            self.publishedAt = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

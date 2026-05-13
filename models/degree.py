from mongoengine import Document, StringField, BooleanField, DateTimeField, EmbeddedDocument, EmbeddedDocumentField, ListField
import datetime


class DegreePolicy(EmbeddedDocument):
    meta = {'strict': False}

    reportLanguage = StringField(default='English')
    reportContentType = StringField(default='Text')
    allowedLanguages = ListField(StringField(), default=list)
    generationInstruction = StringField(default='')
    aiPromptContext = StringField(default='')
    strictLanguageOnly = BooleanField(default=False)
    imagesRequired = BooleanField(default=False)

class Degree(Document):
    meta = {'collection': 'degrees', 'strict': False}
    
    name = StringField(required=True, unique=True)
    policy = EmbeddedDocumentField(DegreePolicy, default=DegreePolicy)
    isActive = BooleanField(default=True)
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

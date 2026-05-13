from mongoengine import (
    Document, StringField, BooleanField, DateTimeField,
    ReferenceField, ListField, EmbeddedDocument,
    EmbeddedDocumentField, IntField
)
import datetime


class ResumeEducation(EmbeddedDocument):
    meta = {'strict': False}
    degreeName = StringField(default='')
    collegeUniversityName = StringField(default='')
    passingYear = StringField(default='')
    percentageCgpa = StringField(default='')
    location = StringField(default='')
    sortOrder = IntField(default=0)


class ResumeExperience(EmbeddedDocument):
    meta = {'strict': False}
    companyName = StringField(default='')
    position = StringField(default='')
    duration = StringField(default='')
    location = StringField(default='')
    responsibilities = StringField(default='')
    rawDutyKeywords = ListField(StringField(), default=list)
    enhancedDuties = StringField(default='')
    sortOrder = IntField(default=0)


class ResumeProject(EmbeddedDocument):
    meta = {'strict': False}
    title = StringField(default='')
    year = StringField(default='')
    projectUrl = StringField(default='')
    githubUrl = StringField(default='')
    description = StringField(default='')
    rawKeywords = ListField(StringField(), default=list)
    enhancedDescription = StringField(default='')
    sortOrder = IntField(default=0)


class ResumeVolunteering(EmbeddedDocument):
    meta = {'strict': False}
    organizationName = StringField(default='')
    role = StringField(default='')
    duration = StringField(default='')
    description = StringField(default='')
    rawContributionKeywords = ListField(StringField(), default=list)
    enhancedContributions = StringField(default='')
    sortOrder = IntField(default=0)


class ResumeCertification(EmbeddedDocument):
    meta = {'strict': False}
    certificationName = StringField(default='')
    issuingAuthority = StringField(default='')
    year = StringField(default='')
    sortOrder = IntField(default=0)


class ResumeLanguage(EmbeddedDocument):
    meta = {'strict': False}
    languageName = StringField(default='')
    proficiency = StringField(
        choices=('', 'Basic', 'Intermediate', 'Advanced', 'Fluent'),
        default=''
    )
    sortOrder = IntField(default=0)


class Resume(Document):
    meta = {'collection': 'resumes', 'strict': False}

    user = ReferenceField('User', required=True)

    title = StringField(default='')

    fullName = StringField(default='')
    address = StringField(default='')
    phone = StringField(default='')
    email = StringField(default='')
    photoUrl = StringField(default='')
    linkedinUrl = StringField(default='')
    githubUrl = StringField(default='')

    careerObjectiveRaw = StringField(default='')
    careerObjectiveEnhanced = StringField(default='')

    education = ListField(EmbeddedDocumentField(ResumeEducation), default=list)
    experience = ListField(EmbeddedDocumentField(ResumeExperience), default=list)

    skills = ListField(StringField(), default=list)
    technicalSkills = ListField(StringField(), default=list)
    coursework = ListField(StringField(), default=list)
    personalSkills = ListField(StringField(), default=list)

    projects = ListField(EmbeddedDocumentField(ResumeProject), default=list)
    volunteering = ListField(EmbeddedDocumentField(ResumeVolunteering), default=list)
    certifications = ListField(EmbeddedDocumentField(ResumeCertification), default=list)
    languages = ListField(EmbeddedDocumentField(ResumeLanguage), default=list)

    status = StringField(
        choices=('draft', 'generating', 'generated', 'downloaded'),
        default='draft'
    )
    errorMessage = StringField(default='')
    downloadCount = IntField(default=0)

    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

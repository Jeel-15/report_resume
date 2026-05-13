from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField, ListField
import datetime

class Industry(Document):
    meta = {'collection': 'industries', 'strict': False}
    
    name = StringField(required=True)
    villageCityName = StringField(default='')
    tehsil = StringField(default='')
    district = StringField(default='')
    state = StringField(default='')
    website = StringField(default='')
    # logo = StringField(default='')
    gstNumber = StringField(default='')
    industryDetails = StringField(default='')       # brief profile/description
    industryType = StringField(default='')          # e.g. Manufacturing, Services, Automobile
    industrySubType = StringField(default='')       # e.g. Development of Software
    keyActivities = ListField(StringField(), default=list)  # bullet list of activities
    approvalStatus = StringField(
        choices=('approved', 'pending', 'rejected'),
        default='approved'                          # IMPORTANT: default='approved' so all existing data stays working
    )
    rejectionReason = StringField(default='')
    createdBy = ReferenceField('User')
    isVerified = BooleanField(default=False)
    isActive = BooleanField(default=True)
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

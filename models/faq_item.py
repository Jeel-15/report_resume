from mongoengine import (
    Document, StringField, BooleanField,
    DateTimeField, IntField
)
import datetime


class FaqItem(Document):
    meta = {'collection': 'faq_items', 'strict': False}

    question   = StringField(required=True)
    answer     = StringField(required=True)
    # Category groups questions: 
    # "About the Platform", "Using the Platform", "Account & Pricing"
    category   = StringField(default='General')
    sortOrder  = IntField(default=0)
    isActive   = BooleanField(default=True)
    createdAt  = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt  = DateTimeField(default=datetime.datetime.utcnow)

    # Default FAQ items (for reference only):
    # 
    # Category: "About the Platform"
    #   - What is ReportGen?
    #   - Which universities are supported?
    #   - How long does report generation take?
    #   - Is it plagiarism to use AI-generated reports?
    #
    # Category: "Using the Platform"
    #   - Can I edit the generated report?
    #   - What does the downloaded PDF look like?
    #   - What is the Resume Builder?
    #
    # Category: "Account & Pricing"
    #   - Is there a free plan?
    #   - Can I generate multiple reports?
    #   - How do I reset my password?

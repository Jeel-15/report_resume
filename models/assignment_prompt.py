"""
AssignmentPrompt — admin-configurable prompt injection rules.

When a session's universityName matches any of trigger_keywords,
the injectedInstruction is appended to the n8n system prompt.
This allows admins to enforce university-specific formatting rules
(e.g., "For GTU, use Continuous Evaluation Matrix format for lab reports")
without touching backend code.
"""
from mongoengine import (
    Document, StringField, BooleanField, DateTimeField,
    ListField, IntField
)
import datetime


class AssignmentPrompt(Document):
    meta = {'collection': 'assignment_prompts', 'strict': False}

    # Human-readable name for admin display
    name = StringField(required=True)

    # Which assignment type this applies to ('*' = all types)
    assignmentType = StringField(default='*')

    # Trigger keywords matched against universityName (case-insensitive)
    # Example: ["GTU", "Gujarat Technological University"]
    triggerKeywords = ListField(StringField(), default=list)

    # The instruction injected into the n8n system prompt
    injectedInstruction = StringField(required=True)

    # Lower sort_order = injected first when multiple prompts match
    sortOrder = IntField(default=0)

    # Filter in Python: [p for p in all if p.isActive]
    isActive = BooleanField(default=True)

    createdAt = DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = DateTimeField(default=datetime.datetime.utcnow)

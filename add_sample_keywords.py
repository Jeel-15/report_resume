#!/usr/bin/env python3
"""
Script to add sample work keywords to the database
This demonstrates the required data structure
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from mongoengine import connect
from models.work_keyword import WorkKeyword
from models.major import Major
from models.industry import Industry

# Connect to the current application database
sqlite_path = os.getenv('SQLITE_PATH', os.path.join(os.path.dirname(__file__), 'data', 'app.db'))
connect('__documents', host=f'sqlite:///{sqlite_path}')

# Get the Gujarati major
gujarati_major = Major.objects(name='Gujarati').first()
if not gujarati_major:
    print("ERROR: Gujarati major not found!")
    print("Available majors:")
    for maj in Major.objects():
        print(f"  - {maj.name}")
    sys.exit(1)

print(f"Found Gujarati major: {gujarati_major.id}")

# Sample keywords for Gujarati major
sample_keywords = [
    {
        'keyword': 'Customer Communication',
        'industryType': 'IVInfotech',
        'jobProfile': 'Content Writer',
        'major': gujarati_major,
        'sortOrder': 1,
    },
    {
        'keyword': 'Content Management',
        'industryType': 'IVInfotech',
        'jobProfile': 'Content Writer',
        'major': gujarati_major,
        'sortOrder': 2,
    },
    {
        'keyword': 'SEO Optimization',
        'industryType': 'IVInfotech',
        'jobProfile': 'Content Writer',
        'major': gujarati_major,
        'sortOrder': 3,
    },
    {
        'keyword': 'Hindi-English Translation',
        'industryType': 'IVInfotech',
        'jobProfile': 'Translator',
        'major': gujarati_major,
        'sortOrder': 4,
    },
    {
        'keyword': 'Data Entry',
        'industryType': 'IVInfotech',
        'jobProfile': 'Data Entry',
        'major': gujarati_major,
        'sortOrder': 5,
    },
]

# Also add universal keywords (no major restriction)
universal_keywords = [
    {
        'keyword': 'Team Collaboration',
        'industryType': 'IVInfotech',
        'jobProfile': '',
        'major': None,
        'sortOrder': 10,
    },
    {
        'keyword': 'Problem Solving',
        'industryType': 'IVInfotech',
        'jobProfile': '',
        'major': None,
        'sortOrder': 11,
    },
    {
        'keyword': 'Time Management',
        'industryType': 'IVInfotech',
        'jobProfile': '',
        'major': None,
        'sortOrder': 12,
    },
]

# Add major-specific keywords
print(f"\nAdding {len(sample_keywords)} major-specific keywords for Gujarati...")
for kw_data in sample_keywords:
    existing = WorkKeyword.objects(
        keyword=kw_data['keyword'],
        industryType=kw_data['industryType'],
        jobProfile=kw_data['jobProfile']
    ).first()
    
    if existing:
        print(f"  ✓ Already exists: {kw_data['keyword']}")
    else:
        kw = WorkKeyword(**kw_data, isActive=True)
        kw.save()
        print(f"  ✓ Created: {kw_data['keyword']}")

# Add universal keywords
print(f"\nAdding {len(universal_keywords)} universal keywords...")
for kw_data in universal_keywords:
    existing = WorkKeyword.objects(
        keyword=kw_data['keyword'],
        industryType=kw_data['industryType']
    ).first()
    
    if existing:
        print(f"  ✓ Already exists: {kw_data['keyword']}")
    else:
        kw = WorkKeyword(**kw_data, isActive=True)
        kw.save()
        print(f"  ✓ Created: {kw_data['keyword']}")

# Verify
total = WorkKeyword.objects.count()
print(f"\n✓ Done! Total keywords in database: {total}")

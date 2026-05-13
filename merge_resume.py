import os

stripped_path = r'templates/student/resume_builder_stripped.html'
backup_path = r'templates/student/resume_builder_backup.html'
output_path = r'templates/student/resume_builder.html'

# 1. Read stripped file
with open(stripped_path, 'r', encoding='utf-8') as f:
    stripped_content = f.read()

# 2. Read backup file lines 841 to 2895 (indexing starts at 0, so 840 to 2895)
with open(backup_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    # Line 841 is index 840. We want from 841 onwards.
    extra_js_content = "".join(lines[840:])

# 3. Combine and Write
final_content = stripped_content.strip() + "\n\n" + extra_js_content

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(final_content)

# 4. Verification
print(f"Merged file written to: {output_path}")
print(f"Total lines in merged file: {len(final_content.splitlines())}")

with open(output_path, 'r', encoding='utf-8') as f:
    content = f.read()
    sections = {
        'title block': '{% block title %}',
        'extra_css': '{% block extra_css %}',
        'content block': '{% block content %}',
        'extra_js': '{% block extra_js %}'
    }
    for name, snippet in sections.items():
        exists = snippet in content
        print(f"Section '{name}' exists: {exists}")

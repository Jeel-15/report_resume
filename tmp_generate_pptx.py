from utils.pptx_generator import generate_pptx_from_sections
sections = [{
    'title': 'Intro',
    'content_markdown': '## Intro\nThis is a sample paragraph.\n\nSpeaker notes: These are notes.',
    'sort_order': 1,
}]
meta = {
    'title': 'Test Deck',
    'assignmentType': 'presentation_script',
    'studentName': 'Test Student',
    'universityName': 'Test Univ',
    'degreeName': 'B.Sc',
    'wordCount': 200,
}
buf = generate_pptx_from_sections(sections, meta)
with open('out.pptx', 'wb') as f:
    f.write(buf.read())
print('Wrote out.pptx')

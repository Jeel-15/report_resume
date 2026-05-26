"""
utils/pptx_generator.py

Build a presentation-style PPTX from assignment sections.
Uses python-pptx and keeps the output simple, readable, and export-friendly.
"""
import io
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt


def _clean_text(value):
    text = '' if value is None else str(value)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _strip_slide_prefix(text):
    value = _clean_text(text)
    value = re.sub(r'(?i)^\s*slide\s*\d+\s*:\s*', '', value)
    return value.strip()


def _strip_inline_markdown(text):
    value = _clean_text(text)
    if not value:
        return value

    # Remove markdown heading markers while keeping the text itself.
    value = re.sub(r'^\s{0,3}#{1,6}\s*', '', value)
    value = re.sub(r'\*\*(.+?)\*\*', r'\1', value)
    value = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', value)
    value = re.sub(r'`([^`]+)`', r'\1', value)
    value = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', value)
    value = re.sub(r'\[(.*?)\]', r'\1', value)
    value = value.replace('—', '-').replace('–', '-')
    value = re.sub(r'[\*_]{2,}', '', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _markdown_to_slide_blocks(markdown_text, slide_title=''):
    """Convert section markdown into structured slide blocks.

    Returns a list of tuples: (kind, text) where kind is one of
    'label', 'bullet', 'number', or 'paragraph'.
    """
    text = _clean_text(markdown_text)
    if not text:
        return []

    blocks = []
    slide_title_norm = _strip_slide_prefix(slide_title).lower()

    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        normalized = _strip_inline_markdown(line)
        if not normalized:
            continue

        # Ignore repeated slide title / speaker note scaffolding already handled by the deck layout.
        if re.match(r'(?i)^\s*slide\s*\d+\s*:\s*', normalized):
            candidate = _strip_slide_prefix(normalized)
            if not candidate or candidate.lower() == slide_title_norm:
                continue
            normalized = candidate

        if re.match(r'(?i)^\s*(speaker\s*notes?|notes)\s*:?[\s-]*$', normalized):
            continue
        if re.match(r'(?i)^\s*---+\s*$', normalized):
            continue

        bullet_match = re.match(r'^[-*•]\s+(.+)', line)
        if bullet_match:
            bullet_text = _strip_inline_markdown(bullet_match.group(1))
            if bullet_text:
                blocks.append(('bullet', bullet_text))
            continue

        num_match = re.match(r'^(\d+)\.\s+(.+)', line)
        if num_match:
            number_text = _strip_inline_markdown(num_match.group(2))
            if number_text:
                blocks.append(('number', f'{num_match.group(1)}. {number_text}'))
            continue

        if line.startswith('|'):
            parts = [part.strip() for part in line.strip('|').split('|') if part.strip()]
            if parts:
                blocks.append(('paragraph', '  '.join(_strip_inline_markdown(part) for part in parts)))
            continue

        # Convert bare emphasis labels like "Headline:" / "Bullet Points:" into clean labels.
        if normalized.endswith(':') and len(normalized) <= 80:
            blocks.append(('label', normalized))
            continue

        blocks.append(('paragraph', normalized))

    return blocks


def _chunk_lines(lines, max_lines=7, max_chars=700):
    chunks = []
    current = []
    current_chars = 0
    for line in lines:
        line_len = len(line)
        if current and (len(current) >= max_lines or current_chars + line_len > max_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(line)
        current_chars += line_len
    if current:
        chunks.append(current)
    return chunks or [[]]


def _add_top_bar(slide, prs, color=RGBColor(0x2A, 0x4C, 0xD6)):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        prs.slide_width,
        Inches(0.25),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()


def _add_textbox(slide, left, top, width, height, text, font_size=24, bold=False, color=RGBColor(0x1A, 0x1A, 0x2E), align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = 'Aptos'
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def generate_pptx_from_sections(sections, metadata):
    """
    Create a PPTX deck from assignment sections.

    Args:
        sections: list of dicts with section_key, title, content_markdown, sort_order
        metadata: dict with title, assignmentType, studentName, universityName, degreeName, wordCount

    Returns:
        io.BytesIO with the PPTX file.
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title = str(metadata.get('title', 'Presentation') or 'Presentation').strip()
    assignment_type_label = {
        'essay': 'Essay',
        'research_paper': 'Research Paper',
        'lab_report': 'Lab Report',
        'case_study': 'Case Study',
        'presentation_script': 'Presentation',
    }.get(str(metadata.get('assignmentType', '') or ''), 'Presentation')
    student_name = str(metadata.get('studentName', '') or '').strip()
    university_name = str(metadata.get('universityName', '') or '').strip()
    degree_name = str(metadata.get('degreeName', '') or '').strip()
    word_count = int(metadata.get('wordCount', 0) or 0)

    sorted_sections = sorted(
        [s for s in sections if isinstance(s, dict)],
        key=lambda item: int(item.get('sort_order', 0) or 0)
    )

    # Cover slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(0xF7, 0xF9, 0xFF)
    _add_top_bar(slide, prs)
    _add_textbox(slide, Inches(0.75), Inches(1.1), Inches(11.6), Inches(1.0), title, font_size=30, bold=True)
    subtitle_bits = [assignment_type_label]
    if degree_name:
        subtitle_bits.append(degree_name)
    if word_count:
        subtitle_bits.append(f'{word_count:,} words')
    _add_textbox(slide, Inches(0.78), Inches(2.05), Inches(11.2), Inches(0.45), '  |  '.join(subtitle_bits), font_size=16, color=RGBColor(0x5B, 0x6B, 0x8A))

    if student_name or university_name:
        owner = '  |  '.join([part for part in [student_name, university_name] if part])
        _add_textbox(slide, Inches(0.78), Inches(2.5), Inches(11.2), Inches(0.38), owner, font_size=13, color=RGBColor(0x6B, 0x7A, 0x96))

    _add_textbox(
        slide,
        Inches(0.78),
        Inches(3.15),
        Inches(11.4),
        Inches(1.0),
        'Use this deck as a clean presentation draft. Edit visuals, speaker notes, and timing before delivery.',
        font_size=16,
        color=RGBColor(0x34, 0x4C, 0x73),
    )

    # Agenda slide
    if sorted_sections:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _add_top_bar(slide, prs, RGBColor(0x4B, 0x6B, 0xF2))
        _add_textbox(slide, Inches(0.65), Inches(0.55), Inches(6.5), Inches(0.5), 'Agenda', font_size=24, bold=True)
        agenda = []
        for idx, sec in enumerate(sorted_sections, start=1):
            agenda.append(f'{idx}. {str(sec.get("title", "Section") or "Section").strip()}')
        agenda_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.3), Inches(11.5), Inches(5.4))
        tf = agenda_box.text_frame
        tf.word_wrap = True
        tf.clear()
        for idx, item in enumerate(agenda):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = item
            run.font.name = 'Aptos'
            run.font.size = Pt(22)
            run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

    # Content slides (improved: reduce over-chunking, preserve speaker notes)
    for sec in sorted_sections:
        section_title = str(sec.get('title', '') or 'Section').strip()
        cleaned_title = _strip_slide_prefix(section_title) or section_title

        # Extract speaker notes block (if present)
        content_md = str(sec.get('content_markdown', '') or '')
        notes_match = re.search(r'(?s)(?:^|\n)speaker\s*notes\s*:\s*(.+)$', content_md, flags=re.IGNORECASE)
        speaker_notes = notes_match.group(1).strip() if notes_match else ''

        # Determine if this section explicitly indicates a slide (prefer single slide)
        is_explicit_slide = bool(re.search(r'(?i)\bslide\b|\btitle slide\b', section_title))

        blocks = _markdown_to_slide_blocks(content_md, slide_title=cleaned_title)

        # Group paragraph-like blocks to avoid tiny-sentence splitting
        grouped_lines = []
        buf = []
        for kind, text in blocks:
            if kind in ('bullet', 'number', 'label'):
                if buf:
                    grouped_lines.append(' '.join(buf).strip())
                    buf = []
                if kind == 'bullet':
                    grouped_lines.append(f'• {text}')
                else:
                    grouped_lines.append(text)
            else:
                buf.append(text)
        if buf:
            grouped_lines.append(' '.join(buf).strip())

        # If explicit slide or reasonably short, keep a single slide for the section
        if is_explicit_slide or (len(grouped_lines) <= 6 and sum(len(l) for l in grouped_lines) <= 1200):
            chunks = [grouped_lines]
        else:
            # Use higher thresholds to avoid producing too many slides
            chunks = _chunk_lines(grouped_lines, max_lines=12, max_chars=1400)

        for chunk_index, chunk in enumerate(chunks, start=1):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = RGBColor(0xF8, 0xFA, 0xFF)
            _add_top_bar(slide, prs)
            heading = cleaned_title if len(chunks) == 1 else f'{cleaned_title} - Part {chunk_index}'
            _add_textbox(slide, Inches(0.7), Inches(0.55), Inches(11.7), Inches(0.5), heading, font_size=22, bold=True)

            content_box = slide.shapes.add_textbox(Inches(0.9), Inches(1.35), Inches(11.4), Inches(5.7))
            tf = content_box.text_frame
            tf.word_wrap = True
            tf.clear()
            if not chunk:
                p = tf.paragraphs[0]
                run = p.add_run()
                run.text = 'Add content to this section.'
                run.font.name = 'Aptos'
                run.font.size = Pt(18)
                run.font.color.rgb = RGBColor(0x7A, 0x87, 0xA2)
            else:
                for idx, line in enumerate(chunk):
                    p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                    run = p.add_run()
                    if line.startswith('• '):
                        p.level = 0
                        run.text = line[2:]
                        run.font.size = Pt(18 if len(line) < 120 else 16)
                    elif re.match(r'^\d+\.\s+', line):
                        run.text = line
                        run.font.size = Pt(18 if len(line) < 120 else 16)
                    elif line.endswith(':') and len(line) <= 120:
                        run.text = line
                        run.font.bold = True
                        run.font.size = Pt(18)
                    else:
                        run.text = line
                        run.font.size = Pt(20 if len(line) < 120 else 16)
                    run.font.name = 'Aptos'
                    run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

            # Add speaker notes (if present)
            if speaker_notes:
                try:
                    notes_slide = slide.notes_slide
                    notes_tf = notes_slide.notes_text_frame
                    notes_tf.clear()
                    notes_tf.text = _strip_inline_markdown(speaker_notes)
                except Exception:
                    pass

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer
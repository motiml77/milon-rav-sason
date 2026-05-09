# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import docx

folder = os.path.dirname(__file__)
docx_files = [f for f in os.listdir(folder) if f.endswith('.docx')]
docx_path = os.path.join(folder, docx_files[0])
doc = docx.Document(docx_path)

# Find paragraph that opens with quote that has "ראוי לדעת למה קראו"
for pi, para in enumerate(doc.paragraphs):
    if 'ראוי לדעת למה קראו' in para.text:
        print(f'\n=== Paragraph {pi} ===')
        print(f'Length: {len(para.text)} chars')
        print(f'First 500 chars: {para.text[:500]!r}')
        print(f'\nLast 200 chars: {para.text[-200:]!r}')
        print(f'\nTotal runs: {len(para.runs)}')

        # Group consecutive runs by their font formatting
        from itertools import groupby
        def fmt_key(r):
            size = r.font.size.pt if r.font.size else None
            return (r.font.name, size, r.bold, r.underline)

        # Show distinct formatting blocks
        print('\n=== Distinct formatting blocks in this paragraph ===')
        for key, group in groupby(para.runs, key=fmt_key):
            chunks = list(group)
            text = ''.join(r.text for r in chunks)
            if not text.strip():
                continue
            print(f'  ({key[0]}, {key[1]}pt, bold={key[2]}, u={key[3]}): {len(text)} chars: {text[:100]!r}')
        break

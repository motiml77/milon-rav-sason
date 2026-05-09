# -*- coding: utf-8 -*-
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import docx

folder = os.path.dirname(__file__)
docx_files = [f for f in os.listdir(folder) if f.endswith('.docx')]
docx_path = os.path.join(folder, docx_files[0])
doc = docx.Document(docx_path)

# Search for paragraphs containing (אורות התחיה or (אוה"ת
for pi, para in enumerate(doc.paragraphs):
    text = para.text
    if 'אורות התחיה' in text or 'כשלומדים תורה לשמה' in text:
        print(f'\n=== Paragraph {pi} ===')
        print(f'Full text (first 500): {text[:500]!r}')
        print('\nRun-by-run breakdown:')
        for ri, run in enumerate(para.runs):
            t = run.text
            if not t.strip():
                continue
            size = run.font.size.pt if run.font.size else None
            name = run.font.name or 'default'
            print(f'  [{ri}] (size={size}pt, font={name}): {t[:100]!r}')
        break

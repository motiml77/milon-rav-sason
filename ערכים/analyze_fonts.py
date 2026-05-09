# -*- coding: utf-8 -*-
import sys, io, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import docx
from collections import Counter

# Find the docx file
folder = os.path.dirname(__file__)
docx_files = [f for f in os.listdir(folder) if f.endswith('.docx')]
print(f'Found docx files: {docx_files}')
docx_path = os.path.join(folder, docx_files[0])
print(f'Opening: {docx_path}')

doc = docx.Document(docx_path)

font_sizes = Counter()
font_names = Counter()
font_combos = Counter()
samples_by_combo = {}

for para in doc.paragraphs:
    for run in para.runs:
        if not run.text.strip():
            continue
        size = run.font.size.pt if run.font.size else None
        name = run.font.name
        font_sizes[size] += 1
        font_names[name] += 1
        combo = (name, size)
        font_combos[combo] += 1
        if combo not in samples_by_combo:
            samples_by_combo[combo] = run.text.strip()[:100]

print('\n=== Font sizes (pt) ===')
for size, count in font_sizes.most_common(15):
    print(f'  {size}: {count}')

print('\n=== Font names ===')
for name, count in font_names.most_common(15):
    print(f'  {name!r}: {count}')

print('\n=== Top combos (font, size) with samples ===')
for combo, count in font_combos.most_common(25):
    sample = samples_by_combo.get(combo, '')
    print(f'  {combo}: {count}')
    print(f'    sample: {sample!r}')

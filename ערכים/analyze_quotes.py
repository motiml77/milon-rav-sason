# -*- coding: utf-8 -*-
"""בודק דוגמאות מתוך הציטוטים החשודים: גופן Aptos / גודל 10.5"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import docx

folder = os.path.dirname(__file__)
docx_files = [f for f in os.listdir(folder) if f.endswith('.docx')]
docx_path = os.path.join(folder, docx_files[0])
doc = docx.Document(docx_path)

# Capture longer samples
aptos_samples = []
size105_samples = []
size115_samples = []

# Walk paragraphs and reconstruct context: surrounding regular text + the special run
for pi, para in enumerate(doc.paragraphs):
    runs = para.runs
    for ri, run in enumerate(runs):
        text = run.text
        if not text.strip():
            continue
        size = run.font.size.pt if run.font.size else None
        name = run.font.name

        # Build context: prev run text + this run + next run text
        prev_text = runs[ri-1].text[-30:] if ri > 0 else ''
        next_text = runs[ri+1].text[:30] if ri < len(runs)-1 else ''

        if name == 'Aptos' and len(aptos_samples) < 8:
            aptos_samples.append((prev_text, text, next_text))
        elif size == 10.5 and len(size105_samples) < 8:
            size105_samples.append((prev_text, text, next_text))
        elif size == 11.5 and len(size115_samples) < 8:
            size115_samples.append((prev_text, text, next_text))

print('=== Aptos font samples (with surrounding context) ===')
for prev, txt, nxt in aptos_samples:
    print(f'  ...{prev!r} || >>> {txt!r} <<< || {nxt!r}...')
    print()

print('\n=== Size 10.5pt samples ===')
for prev, txt, nxt in size105_samples:
    print(f'  ...{prev!r} || >>> {txt!r} <<< || {nxt!r}...')
    print()

print('\n=== Size 11.5pt samples ===')
for prev, txt, nxt in size115_samples:
    print(f'  ...{prev!r} || >>> {txt!r} <<< || {nxt!r}...')
    print()

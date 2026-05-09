# -*- coding: utf-8 -*-
"""בדיקה מדויקת של regex על הציטוט"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Run on RAW data.js content (not wrapped) to see the actual original
import json, os
folder = r'C:\Users\Moti Levi\Desktop\AI\rav sason\ערכים'
with open(os.path.join(folder, 'data.js'), encoding='utf-8') as f:
    content = f.read().strip()
m = re.match(r'^const\s+\w+\s*=\s*', content)
if m:
    content = content[m.end():]
content = content.rstrip().rstrip(";")
raw = json.loads(content)

QUOTE_INLINE = re.compile(
    r'(?<=[\s:>])'
    r'"'
    r'((?:[^"]|"(?![\s.,;:<]|$))+?)'
    r'"'
    r'(?=[\s.,;:<]|$)',
    re.DOTALL
)

# Find the relevant entry's third definition
for section in raw['sections']:
    for term in section['terms']:
        for i, definition in enumerate(term['definition']):
            if 'ראוי לדעת למה קראו' in definition:
                text = definition
                print(f'Term: {term["term"]}')
                print(f'Length: {len(text)}')
                # Find all matches
                matches = list(QUOTE_INLINE.finditer(text))
                print(f'\nMatches: {len(matches)}')
                for m in matches:
                    inner = m.group(1)
                    plain = re.sub(r'<[^>]+>', '', inner)
                    print(f'  match start={m.start()} end={m.end()} content_len={len(plain)}')
                    print(f'    last 80 chars of match: {text[max(m.start(), m.end()-80):m.end()]!r}')
                print()
                # Find positions of all " in text
                print('=== All " positions in text ===')
                for j, ch in enumerate(text):
                    if ch == '"':
                        ctx = text[max(0,j-15):j+15]
                        print(f'  pos {j}: {ctx!r}')
                break
        else:
            continue
        break
    else:
        continue
    break

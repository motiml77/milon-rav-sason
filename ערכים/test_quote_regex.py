# -*- coding: utf-8 -*-
import json, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'C:\Users\Moti Levi\Desktop\AI\rav sason\data.json', encoding='utf-8') as f:
    data = json.load(f)

QUOTE_INLINE = re.compile(
    r'(?<=[\s:>])'
    r'"'
    r'((?:[^"]|"(?=[֐-׿]))+?)'
    r'"'
    r'(?=[\s.,;:<]|$)',
    re.DOTALL
)

for t in data['topics']:
    for e in t['entries']:
        for i, d in enumerate(e['definitions']):
            if 'ראוי לדעת למה קראו' in d['text']:
                text = d['text']
                # Remove existing quote wrap to test fresh
                clean = re.sub(r'<span class="quote">|</span>', lambda m: '' if m.group(0) == '<span class="quote">' else '', text, count=2)
                # Actually just test on text as-is
                matches = list(QUOTE_INLINE.finditer(text))
                print(f'Matches: {len(matches)}')
                for m in matches:
                    plain = re.sub(r'<[^>]+>', '', m.group(1))
                    print(f'  start={m.start()} end={m.end()} len={len(plain)}')
                    print(f'    head: {plain[:60]}')
                    print(f'    tail: {plain[-60:]}')
                # Try just the second quote area
                print()
                print('=== Trying just on text from pos 525 onwards ===')
                sub = text[525:]
                matches2 = list(QUOTE_INLINE.finditer(sub))
                print(f'Matches in sub: {len(matches2)}')
                for m in matches2:
                    plain = re.sub(r'<[^>]+>', '', m.group(1))
                    print(f'  len={len(plain)}')
                    print(f'    head: {plain[:60]}')
                    print(f'    tail: {plain[-60:]}')
                break

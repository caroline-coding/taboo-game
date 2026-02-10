#!/usr/bin/env python3
import anthropic
import json
import re
import time

client = anthropic.Anthropic()

with open('cards.json') as f:
    cards = json.load(f)

existing_words = set(card['word'].lower() for card in cards)
print(f'Starting with {len(cards)} cards')

categories = [
    {'name': 'Sports teams, athletes, and sporting events', 'difficulty': 'medium', 'count': 60},
    {'name': 'Musical artists, bands, albums, and songs', 'difficulty': 'medium', 'count': 60},
    {'name': 'Video games, board games, and card games', 'difficulty': 'medium', 'count': 50},
    {'name': 'Fashion brands, designers, and clothing styles', 'difficulty': 'medium', 'count': 40},
    {'name': 'Scientific discoveries and inventions', 'difficulty': 'hard', 'count': 50},
    {'name': 'Mythological figures and folklore', 'difficulty': 'hard', 'count': 40},
    {'name': 'Architecture, art movements, and artists', 'difficulty': 'expert', 'count': 40},
]

def fix_cap(word):
    words = word.split()
    if len(words) == 1:
        return words[0].capitalize()
    lowercases = {'a','an','the','and','or','but','in','on','at','to','for','of','with','by','from','party','cake','ball','game','day','night','cream','sauce'}
    result = [words[0].capitalize()]
    for w in words[1:]:
        result.append(w.lower() if w.lower() in lowercases else w)
    return ' '.join(result)

def is_bad_taboo(main, taboo):
    m = main.lower().replace(' ', '')
    t = taboo.lower()
    if ' ' in taboo.strip(): return True
    if t == m: return True
    if len(t) >= 3 and t in m: return True
    if len(m) >= 3 and m in t: return True
    return False

total_added = 0
target = 260

for cat in categories:
    if total_added >= target:
        break
    needed = min(cat['count'], target - total_added)
    print(f"\n[{cat['difficulty'].upper()}] {cat['name']}: {needed}...")

    sample = list(existing_words)[:100]
    prompt = f"""Generate exactly {needed} Taboo cards for: {cat['name']}
Difficulty: {cat['difficulty']}

RULES:
1. Target word: 1-2 words ONLY
2. Exactly 5 single-word taboo words
3. Taboo words cannot be part of or forms of target word
4. Proper capitalization only for proper nouns

AVOID: {', '.join(sample[:50])}

Return ONLY JSON: [{{"word": "Example", "taboo": ["clue1", "clue2", "clue3", "clue4", "clue5"], "difficulty": "{cat['difficulty']}"}}]"""

    try:
        resp = client.messages.create(model='claude-sonnet-4-20250514', max_tokens=8000, messages=[{'role': 'user', 'content': prompt}])
        text = resp.content[0].text.strip()
        if '```' in text:
            m = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            text = m.group(1) if m else ''
        new_cards = json.loads(text)

        added = 0
        for card in new_cards:
            if len(card['word'].split()) > 2:
                continue
            card['word'] = fix_cap(card['word'])
            good_taboos = [t.lower() for t in card['taboo'] if not is_bad_taboo(card['word'], t)]
            if len(good_taboos) >= 3 and card['word'].lower() not in existing_words:
                card['taboo'] = good_taboos[:5]
                card['category'] = cat['name']
                cards.append(card)
                existing_words.add(card['word'].lower())
                added += 1

        total_added += added
        print(f'  Added {added} (total new: {total_added})')
    except Exception as e:
        print(f'  Error: {e}')
    time.sleep(0.5)

with open('cards.json', 'w') as f:
    json.dump(cards, f, indent=2)

print(f'\nTotal cards now: {len(cards)}')

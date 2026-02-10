#!/usr/bin/env python3
"""Fix capitalization of taboo words - proper nouns should be capitalized."""

import anthropic
import json
import re
import time

client = anthropic.Anthropic()

with open('cards.json') as f:
    cards = json.load(f)

print(f'Fixing taboo word capitalization for {len(cards)} cards...')

# Collect all unique taboo words
all_taboo_words = set()
for card in cards:
    for t in card['taboo']:
        all_taboo_words.add(t.lower())

print(f'Found {len(all_taboo_words)} unique taboo words')

# Process in batches to determine which are proper nouns
batch_size = 200
taboo_list = list(all_taboo_words)
capitalization_map = {}

for i in range(0, len(taboo_list), batch_size):
    batch = taboo_list[i:i+batch_size]
    print(f'Processing batch {i//batch_size + 1}/{(len(taboo_list) + batch_size - 1)//batch_size}...')

    prompt = f"""For each word below, determine the correct capitalization.
- Proper nouns (names, places, brands, etc.) should be capitalized: "Disney", "America", "Einstein"
- Regular words should be lowercase: "dog", "running", "blue"

Words to check:
{json.dumps(batch)}

Return ONLY a JSON object mapping lowercase words to their correct capitalization:
{{"disney": "Disney", "america": "America", "dog": "dog", "running": "running"}}"""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = resp.content[0].text.strip()
        if '```' in text:
            m = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            text = m.group(1) if m else '{}'

        corrections = json.loads(text)
        capitalization_map.update(corrections)

    except Exception as e:
        print(f'  Error: {e}')
        # Default to lowercase for failed batches
        for word in batch:
            if word not in capitalization_map:
                capitalization_map[word] = word

    time.sleep(0.2)

# Apply corrections to all cards
print('\nApplying corrections...')
for card in cards:
    card['taboo'] = [capitalization_map.get(t.lower(), t) for t in card['taboo']]

# Save
with open('cards.json', 'w') as f:
    json.dump(cards, f, indent=2)

# Show some examples
print('\nSample proper noun taboo words:')
proper_nouns = [(k, v) for k, v in capitalization_map.items() if v != k.lower() and v[0].isupper()]
for k, v in proper_nouns[:20]:
    print(f'  {k} -> {v}')

print(f'\nDone! Fixed capitalization on {len(cards)} cards')

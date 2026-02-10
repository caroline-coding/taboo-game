#!/usr/bin/env python3
"""
Review and fix Taboo cards:
1. Remove duplicate forms of taboo words (donut/donuts)
2. Fix proper noun capitalization
3. Ensure every card has exactly 5 taboo words
"""

import anthropic
import json
import re
import time

client = anthropic.Anthropic()

def get_stem(word):
    """Get a simple word stem for comparison."""
    w = word.lower()
    # Remove common suffixes
    for suffix in ['ing', 'ed', 'er', 'est', 'ly', 's', 'es', 'ies', 'tion', 'ness', 'ment']:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w

def find_duplicate_forms(taboo_list):
    """Find taboo words that are forms of each other."""
    duplicates = []
    stems = {}

    for t in taboo_list:
        stem = get_stem(t)
        if stem in stems:
            duplicates.append((stems[stem], t))
        else:
            stems[stem] = t

    return duplicates

def dedupe_taboo_words(taboo_list):
    """Remove duplicate forms, keeping the first occurrence."""
    seen_stems = {}
    result = []

    for t in taboo_list:
        stem = get_stem(t)
        if stem not in seen_stems:
            seen_stems[stem] = t
            result.append(t)

    return result

# Load cards
with open('cards.json') as f:
    cards = json.load(f)

print(f'Reviewing {len(cards)} cards...\n')

# Step 1: Find cards with duplicate form taboo words
print('Step 1: Finding duplicate taboo word forms...')
cards_with_dupes = []
for card in cards:
    dupes = find_duplicate_forms(card['taboo'])
    if dupes:
        cards_with_dupes.append((card, dupes))

print(f'  Found {len(cards_with_dupes)} cards with duplicate forms')
if cards_with_dupes[:5]:
    print('  Examples:')
    for card, dupes in cards_with_dupes[:5]:
        print(f"    {card['word']}: {dupes}")

# Deduplicate taboo words
for card in cards:
    card['taboo'] = dedupe_taboo_words(card['taboo'])

# Step 2: Find cards needing more taboo words
print('\nStep 2: Finding cards with <5 taboo words...')
cards_needing_taboos = [c for c in cards if len(c['taboo']) < 5]
print(f'  Found {len(cards_needing_taboos)} cards needing more taboo words')

# Step 3: Collect all taboo words for proper noun check
print('\nStep 3: Collecting taboo words for proper noun check...')
all_taboo_words = set()
for card in cards:
    for t in card['taboo']:
        all_taboo_words.add(t.lower())

# Also add the words that need more taboos - we'll fix everything together
words_needing_fix = []
for card in cards_needing_taboos:
    words_needing_fix.append({
        'word': card['word'],
        'current_taboos': card['taboo'],
        'needed': 5 - len(card['taboo'])
    })

print(f'  {len(all_taboo_words)} unique taboo words to check')

# Process in batches - fix proper nouns AND generate missing taboo words
batch_size = 30
capitalization_map = {}

# First, get proper noun capitalization for all taboo words
print('\nStep 4: Fixing proper noun capitalization...')
taboo_list = list(all_taboo_words)

for i in range(0, len(taboo_list), 200):
    batch = taboo_list[i:i+200]
    print(f'  Checking batch {i//200 + 1}/{(len(taboo_list) + 199)//200}...')

    prompt = f"""For each word, return the correct capitalization.
Proper nouns (names, places, brands, countries, etc.) should be capitalized.
Regular words should be lowercase.

Words: {json.dumps(batch)}

Return JSON mapping lowercase to correct form:
{{"india": "India", "disney": "Disney", "dog": "dog"}}"""

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
        print(f'    Error: {e}')
        for w in batch:
            if w not in capitalization_map:
                capitalization_map[w] = w
    time.sleep(0.2)

# Apply capitalization fixes
for card in cards:
    card['taboo'] = [capitalization_map.get(t.lower(), t) for t in card['taboo']]

# Step 5: Generate missing taboo words
print('\nStep 5: Generating missing taboo words...')
if words_needing_fix:
    for i in range(0, len(words_needing_fix), batch_size):
        batch = words_needing_fix[i:i+batch_size]
        print(f'  Processing batch {i//batch_size + 1}/{(len(words_needing_fix) + batch_size - 1)//batch_size}...')

        prompt_parts = ["Generate additional taboo words for these Taboo cards. Each taboo word must be a SINGLE word, not a form of the target word, and not a form of existing taboo words.\n"]

        for item in batch:
            prompt_parts.append(f"Word: \"{item['word']}\"")
            prompt_parts.append(f"  Current taboos: {item['current_taboos']}")
            prompt_parts.append(f"  Need {item['needed']} more")
            prompt_parts.append("")

        prompt_parts.append("Return JSON mapping each word to a list of new taboo words:")
        prompt_parts.append('{"Word1": ["new1", "new2"], "Word2": ["new1"]}')

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": "\n".join(prompt_parts)}]
            )
            text = resp.content[0].text.strip()
            if '```' in text:
                m = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
                text = m.group(1) if m else '{}'
            new_taboos = json.loads(text)

            # Apply new taboo words
            for card in cards:
                if card['word'] in new_taboos:
                    existing = set(t.lower() for t in card['taboo'])
                    for new_t in new_taboos[card['word']]:
                        if new_t.lower() not in existing and len(card['taboo']) < 5:
                            # Apply proper capitalization
                            card['taboo'].append(capitalization_map.get(new_t.lower(), new_t))
                            existing.add(new_t.lower())
        except Exception as e:
            print(f'    Error: {e}')

        time.sleep(0.3)

# Final check
still_short = [c for c in cards if len(c['taboo']) < 5]
print(f'\n  Cards still with <5 taboo words: {len(still_short)}')

# Save
with open('cards.json', 'w') as f:
    json.dump(cards, f, indent=2)

print(f'\nSaved {len(cards)} cards')

# Summary
print('\n' + '='*50)
print('Summary:')
print(f'  Total cards: {len(cards)}')
print(f'  Fixed duplicate forms: {len(cards_with_dupes)}')
print(f'  Cards that needed more taboos: {len(cards_needing_taboos)}')
print(f'  Cards still short (will need manual fix): {len(still_short)}')

if still_short[:5]:
    print('\n  Examples of cards still short:')
    for c in still_short[:5]:
        print(f"    {c['word']}: {c['taboo']} ({len(c['taboo'])} words)")

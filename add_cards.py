#!/usr/bin/env python3
"""
Generate 500 more Taboo cards and fix capitalization on all cards.
Constraints:
- Target words: 1-2 words only
- Taboo words: single words only
- Taboo words can't overlap with main word
- Proper capitalization (only proper nouns capitalized)
"""

import anthropic
import json
import re
import sys
import time

client = anthropic.Anthropic()

CARDS_FILE = "cards.json"

# Categories for new cards - mix of difficulties
NEW_CATEGORIES = [
    {"name": "Common objects and everyday items", "difficulty": "easy", "count": 80},
    {"name": "Animals and creatures", "difficulty": "easy", "count": 60},
    {"name": "Food, cooking, and cuisine", "difficulty": "easy", "count": 60},
    {"name": "Famous people, celebrities, historical figures", "difficulty": "medium", "count": 80},
    {"name": "Movies, TV shows, books, and media", "difficulty": "medium", "count": 60},
    {"name": "Science, nature, and technology", "difficulty": "medium", "count": 50},
    {"name": "Abstract concepts and emotions", "difficulty": "hard", "count": 60},
    {"name": "Rare words and obscure terms", "difficulty": "expert", "count": 50},
]

def flush_print(msg):
    print(msg)
    sys.stdout.flush()

def is_proper_noun(word):
    """Check if a word is likely a proper noun using Claude."""
    # Common patterns that are proper nouns
    proper_patterns = [
        r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Two capitalized words (names)
    ]

    # These are common words that should NOT be capitalized
    common_words = {
        'party', 'cake', 'ball', 'game', 'house', 'tree', 'car', 'book', 'phone',
        'computer', 'table', 'chair', 'door', 'window', 'water', 'food', 'music',
        'movie', 'show', 'day', 'night', 'morning', 'evening', 'summer', 'winter',
        'spring', 'fall', 'autumn', 'birthday', 'wedding', 'holiday', 'vacation',
        'dinner', 'lunch', 'breakfast', 'coffee', 'tea', 'beer', 'wine', 'dance',
        'song', 'story', 'letter', 'card', 'gift', 'present', 'surprise', 'secret'
    }

    words = word.split()
    if len(words) == 1:
        return word.lower() not in common_words and word[0].isupper()

    # For multi-word, check if it's a known proper noun pattern
    return False

def fix_capitalization(word):
    """Fix capitalization - only proper nouns should be capitalized."""
    words = word.split()

    if len(words) == 1:
        # Single word - capitalize first letter only
        return words[0].capitalize()

    # Multi-word phrase
    result = []
    for i, w in enumerate(words):
        if i == 0:
            # First word always capitalized
            result.append(w.capitalize())
        else:
            # Subsequent words - lowercase unless proper noun indicators
            # Keep capitalized if it looks like a proper noun (name, place, brand)
            w_lower = w.lower()

            # List of words that should stay lowercase
            lowercase_words = {
                'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after',
                'party', 'cake', 'ball', 'game', 'house', 'tree', 'car', 'day',
                'night', 'room', 'box', 'bag', 'cup', 'glass', 'plate', 'bowl',
                'machine', 'station', 'shop', 'store', 'bar', 'club', 'ring',
                'dance', 'song', 'show', 'trip', 'ride', 'race', 'fight', 'match',
                'cream', 'sauce', 'juice', 'bread', 'meat', 'fish', 'chicken',
                'salad', 'soup', 'pie', 'cookie', 'candy', 'chips', 'fries',
                'burger', 'sandwich', 'pizza', 'taco', 'sushi', 'pasta', 'rice',
                'beans', 'corn', 'potato', 'tomato', 'cheese', 'butter', 'oil',
                'salt', 'pepper', 'sugar', 'flour', 'egg', 'milk', 'water',
                'wine', 'beer', 'coffee', 'tea', 'soda', 'pop', 'cocktail'
            }

            if w_lower in lowercase_words:
                result.append(w_lower)
            else:
                # Keep original capitalization for potential proper nouns
                result.append(w)

    return ' '.join(result)

def is_problematic_taboo(main_word, taboo):
    """Check if a taboo word violates the rules."""
    main_lower = main_word.lower().replace(" ", "")
    taboo_lower = taboo.lower()

    if ' ' in taboo.strip():
        return True
    if taboo_lower == main_lower:
        return True
    if len(taboo_lower) >= 3 and taboo_lower in main_lower:
        return True
    if len(main_lower) >= 3 and main_lower in taboo_lower:
        return True

    def get_stem(word):
        w = word.lower()
        for suffix in ['ing', 'ed', 'er', 'est', 'ly', 's', 'es', 'tion', 'ness']:
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                return w[:-len(suffix)]
        return w

    if get_stem(main_lower) == get_stem(taboo_lower):
        return True

    return False

def generate_cards_batch(category, count, existing_words):
    """Generate a batch of cards."""
    sample_existing = list(existing_words)[:100]

    prompt = f"""Generate exactly {count} Taboo cards for: {category['name']}
Difficulty: {category['difficulty']}

STRICT RULES:
1. Target word: 1-2 words ONLY (no 3+ word phrases)
2. Each card has exactly 5 taboo words
3. Taboo words must be SINGLE words only
4. Taboo words cannot be part of the target word (e.g., "ball" is not allowed for "football")
5. Taboo words cannot be forms of the target word (e.g., "running" not allowed for "run")
6. Proper capitalization: Only capitalize proper nouns (names, places, brands). "Birthday party" not "Birthday Party"

AVOID duplicating: {', '.join(sample_existing[:50]) if sample_existing else 'none'}

Return ONLY JSON array:
[{{"word": "Ice cream", "taboo": ["cold", "frozen", "dessert", "vanilla", "cone"], "difficulty": "{category['difficulty']}"}}]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if "```" in text:
            text = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            text = text.group(1) if text else ""

        cards = json.loads(text)

        # Validate and fix cards
        valid_cards = []
        for card in cards:
            # Skip 3+ word cards
            if len(card['word'].split()) > 2:
                continue

            # Fix capitalization
            card['word'] = fix_capitalization(card['word'])

            # Filter and fix taboo words
            good_taboos = []
            for t in card['taboo']:
                if not is_problematic_taboo(card['word'], t):
                    # Lowercase taboo words
                    good_taboos.append(t.lower())

            if len(good_taboos) >= 3:  # Need at least 3 valid taboo words
                card['taboo'] = good_taboos[:5]
                valid_cards.append(card)

        return valid_cards
    except Exception as e:
        flush_print(f"  Error: {e}")
        return []

def fix_all_capitalization(cards):
    """Fix capitalization on all cards using Claude for proper noun detection."""
    flush_print("\nFixing capitalization on all cards...")

    # Batch cards for capitalization check
    words_to_check = list(set(card['word'] for card in cards))

    # Use Claude to identify proper nouns in batches
    batch_size = 100
    proper_nouns = set()

    for i in range(0, len(words_to_check), batch_size):
        batch = words_to_check[i:i+batch_size]
        flush_print(f"  Checking batch {i//batch_size + 1}/{(len(words_to_check) + batch_size - 1)//batch_size}...")

        prompt = f"""For each word/phrase below, determine if it contains proper nouns that should be capitalized.
Return a JSON object where keys are the original words and values are the correctly capitalized versions.

Rules:
- Regular words should only have first letter capitalized: "Birthday party" not "Birthday Party"
- Proper nouns (names, places, brands, titles) keep their capitals: "New York", "Harry Potter", "Coca-Cola"
- Movie/book/show titles: keep standard title capitalization
- Food items: generally lowercase after first word unless brand name

Words to check:
{json.dumps(batch)}

Return ONLY JSON like: {{"Birthday Party": "Birthday party", "New York": "New York", "Harry Potter": "Harry Potter"}}"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            if "```" in text:
                text = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
                text = text.group(1) if text else "{}"

            corrections = json.loads(text)

            # Apply corrections to cards
            for card in cards:
                if card['word'] in corrections:
                    card['word'] = corrections[card['word']]

        except Exception as e:
            flush_print(f"  Error in batch: {e}")
            continue

        time.sleep(0.3)

    return cards

def main():
    flush_print("Adding 500 Cards + Fixing Capitalization")
    flush_print("=" * 50)

    # Load existing cards
    with open(CARDS_FILE) as f:
        cards = json.load(f)

    existing_words = set(card['word'].lower() for card in cards)
    flush_print(f"Starting with {len(cards)} existing cards")

    # Generate new cards
    total_new = 0
    target = 500

    for category in NEW_CATEGORIES:
        if total_new >= target:
            break

        needed = min(category['count'], target - total_new)
        flush_print(f"\n[{category['difficulty'].upper()}] {category['name']}: generating {needed}...")

        new_cards = generate_cards_batch(category, needed, existing_words)

        # Deduplicate
        added = 0
        for card in new_cards:
            if card['word'].lower() not in existing_words:
                card['category'] = category['name']
                cards.append(card)
                existing_words.add(card['word'].lower())
                added += 1

        total_new += added
        flush_print(f"  Added {added} cards (total new: {total_new})")
        time.sleep(0.5)

    flush_print(f"\n{'=' * 50}")
    flush_print(f"Generated {total_new} new cards")

    # Fix capitalization on ALL cards
    cards = fix_all_capitalization(cards)

    # Also lowercase all taboo words
    for card in cards:
        card['taboo'] = [t.lower() for t in card['taboo']]

    # Save
    with open(CARDS_FILE, 'w') as f:
        json.dump(cards, f, indent=2)

    flush_print(f"\nSaved {len(cards)} total cards to {CARDS_FILE}")

if __name__ == "__main__":
    main()

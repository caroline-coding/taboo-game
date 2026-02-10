#!/usr/bin/env python3
"""
Clean up Taboo cards:
1. Remove cards with 3+ word phrases
2. Fix taboo words that violate rules:
   - Must be single words
   - Cannot be the same as main word
   - Cannot be a form of main word
   - Cannot be a substring of main word
"""

import json
import anthropic
import re
import sys

client = anthropic.Anthropic()

def is_problematic_taboo(main_word, taboo):
    """Check if a taboo word violates the rules."""
    main_lower = main_word.lower().replace(" ", "")
    taboo_lower = taboo.lower()

    # Multi-word taboo
    if ' ' in taboo.strip():
        return True, "multi-word"

    # Exact match
    if taboo_lower == main_lower:
        return True, "exact match"

    # Taboo is substring of main word (if taboo is 3+ chars)
    if len(taboo_lower) >= 3 and taboo_lower in main_lower:
        return True, "substring of main"

    # Main word is substring of taboo (forms like "running" for "run")
    if len(main_lower) >= 3 and main_lower in taboo_lower:
        return True, "main is substring"

    # Check for common word forms (simplified check)
    # Strip common suffixes and compare stems
    def get_stem(word):
        w = word.lower()
        for suffix in ['ing', 'ed', 'er', 'est', 'ly', 's', 'es', 'tion', 'ness']:
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                return w[:-len(suffix)]
        return w

    if get_stem(main_lower) == get_stem(taboo_lower):
        return True, "same stem"

    return False, None

def get_replacement_taboos(cards_needing_fixes):
    """Use Claude to generate replacement taboo words."""
    if not cards_needing_fixes:
        return {}

    # Build prompt
    prompt_parts = ["For each word below, I need replacement taboo words for a Taboo game. The taboo words should be single words that are clues/associations but NOT:\n- The same as the main word\n- A form of the main word (e.g., 'running' for 'run')\n- Part of the main word (e.g., 'ball' for 'football')\n\nReturn JSON mapping each word to a list of replacement taboo words.\n\n"]

    for card, bad_taboos, good_taboos in cards_needing_fixes:
        prompt_parts.append(f"Word: \"{card['word']}\"")
        prompt_parts.append(f"  Keep these taboo words: {good_taboos}")
        prompt_parts.append(f"  Need {len(bad_taboos)} replacements for: {bad_taboos}")
        prompt_parts.append("")

    prompt_parts.append("\nReturn ONLY valid JSON like: {\"Word1\": [\"replacement1\", \"replacement2\"], \"Word2\": [\"repl1\"]}")

    prompt = "\n".join(prompt_parts)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    # Extract JSON from response
    if "```" in text:
        text = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL).group(1)

    return json.loads(text)

def main():
    print("Loading cards...")
    with open('cards.json') as f:
        cards = json.load(f)

    print(f"Loaded {len(cards)} cards")

    # Step 1: Remove 3+ word cards
    original_count = len(cards)
    cards = [c for c in cards if len(c['word'].split()) <= 2]
    removed_count = original_count - len(cards)
    print(f"Removed {removed_count} cards with 3+ words, {len(cards)} remaining")

    # Step 2: Find cards with problematic taboo words
    cards_needing_fixes = []
    total_bad_taboos = 0

    for card in cards:
        bad_taboos = []
        good_taboos = []

        for taboo in card['taboo']:
            is_bad, reason = is_problematic_taboo(card['word'], taboo)
            if is_bad:
                bad_taboos.append(taboo)
                total_bad_taboos += 1
            else:
                good_taboos.append(taboo)

        if bad_taboos:
            cards_needing_fixes.append((card, bad_taboos, good_taboos))

    print(f"Found {len(cards_needing_fixes)} cards with problematic taboo words")
    print(f"Total problematic taboo words: {total_bad_taboos}")

    if not cards_needing_fixes:
        print("No fixes needed!")
        return

    # Step 3: Get replacements in batches
    print("\nGenerating replacement taboo words...")
    batch_size = 50
    all_replacements = {}

    for i in range(0, len(cards_needing_fixes), batch_size):
        batch = cards_needing_fixes[i:i+batch_size]
        print(f"  Processing batch {i//batch_size + 1}/{(len(cards_needing_fixes) + batch_size - 1)//batch_size}...")

        try:
            replacements = get_replacement_taboos(batch)
            all_replacements.update(replacements)
        except Exception as e:
            print(f"  Error in batch: {e}")
            continue

    # Step 4: Apply fixes
    print("\nApplying fixes...")
    fixed_count = 0

    for card, bad_taboos, good_taboos in cards_needing_fixes:
        word = card['word']
        if word in all_replacements:
            new_taboos = all_replacements[word]
            # Combine good taboos with new replacements
            card['taboo'] = good_taboos + new_taboos[:len(bad_taboos)]
            # Ensure we have exactly 5 taboo words
            card['taboo'] = card['taboo'][:5]
            while len(card['taboo']) < 5:
                card['taboo'].append("clue")  # Fallback
            fixed_count += 1

    print(f"Fixed {fixed_count} cards")

    # Step 5: Save
    print("\nSaving cards.json...")
    with open('cards.json', 'w') as f:
        json.dump(cards, f, indent=2)

    print(f"Done! Final card count: {len(cards)}")

if __name__ == "__main__":
    main()

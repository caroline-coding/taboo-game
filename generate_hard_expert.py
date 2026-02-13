#!/usr/bin/env python3
"""
Generate hard/expert Taboo cards from GRE/Barron's/SAT word lists.
Sends batches to Anthropic API to select good cards and generate taboo words.
"""

import anthropic
import json
import os
import sys
import time

CARDS_FILE = "cards.json"
CANDIDATES_FILE = "hard_expert_candidates_clean.json"
NEW_CARDS_FILE = "new_hard_expert_cards.json"

def flush_print(msg):
    print(msg)
    sys.stdout.flush()


def generate_taboo_batch(client, words, existing_words_sample):
    """Send a batch of words to the API, get back good taboo cards."""

    prompt = f"""I have a list of words from GRE/SAT vocabulary lists. I want to make Taboo cards from them.

For each word below, decide if it would make a GOOD Taboo card. A good Taboo word is:
- A word most educated English speakers would recognize and could describe
- Something a person could give clues about without using obvious related words
- NOT too obscure (players should have a reasonable chance of guessing)
- NOT a simple common word (should be at least moderately challenging)

For each GOOD word, generate exactly 5 taboo words (the most obvious clues someone would give).
Capitalize the main word naturally.

Also assign a difficulty:
- "hard": Words that most college-educated adults would know but might need to think about (e.g., Metamorphosis, Oligarchy, Stoicism, Paradox)
- "expert": Words that only well-read or specialized people would know (e.g., Solipsism, Hegemony, Epistemology, Dialectic)

Words to evaluate:
{', '.join(words)}

IMPORTANT: Only include words that make genuinely good Taboo cards. Reject words that are:
- Too obscure for anyone to guess
- Simple verb forms or adjectives that aren't fun to describe
- Misspelled variants of other words

Do NOT include any of these existing words: {', '.join(list(existing_words_sample)[:100])}

Return ONLY a JSON array (no other text):
[{{"word": "Metamorphosis", "taboo": ["change", "transform", "butterfly", "Kafka", "caterpillar"], "difficulty": "hard"}}]

If none of the words are good, return an empty array: []"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        cards = json.loads(text)
        return cards

    except Exception as e:
        flush_print(f"  Error: {e}")
        return []


def main():
    flush_print("=" * 60)
    flush_print("Hard/Expert Card Generator - GRE/Barron's/SAT Pipeline")
    flush_print("=" * 60)

    # Load existing cards
    with open(CARDS_FILE) as f:
        existing_cards = json.load(f)
    existing_words = set(c['word'].lower() for c in existing_cards)
    flush_print(f"Existing cards: {len(existing_cards)}")

    # Load candidates
    with open(CANDIDATES_FILE) as f:
        candidates = json.load(f)
    flush_print(f"Candidates: {len(candidates)}")

    # Initialize API client
    client = anthropic.Anthropic()

    # Load progress file if it exists
    if os.path.exists(NEW_CARDS_FILE):
        with open(NEW_CARDS_FILE) as f:
            new_cards = json.load(f)
        flush_print(f"Resuming with {len(new_cards)} previously generated cards")
    else:
        new_cards = []

    new_words = set(c['word'].lower() for c in new_cards)
    all_existing = existing_words | new_words

    # Process in batches
    batch_size = 150
    target_hard = 300
    target_expert = 150

    hard_count = sum(1 for c in new_cards if c.get('difficulty') == 'hard')
    expert_count = sum(1 for c in new_cards if c.get('difficulty') == 'expert')

    flush_print(f"Current: hard={hard_count}, expert={expert_count}")
    flush_print(f"Targets: hard={target_hard}, expert={target_expert}")

    offset = 0
    batch_num = 0

    while offset < len(candidates):
        if hard_count >= target_hard and expert_count >= target_expert:
            flush_print("Targets reached!")
            break

        batch = candidates[offset:offset + batch_size]
        offset += batch_size
        batch_num += 1

        if not batch:
            break

        flush_print(f"\n  Batch {batch_num}: {len(batch)} words...")
        cards = generate_taboo_batch(client, batch, all_existing)

        # Deduplicate and add
        added_hard = 0
        added_expert = 0
        for card in cards:
            w = card['word'].lower()
            if w not in all_existing:
                new_cards.append(card)
                all_existing.add(w)
                if card.get('difficulty') == 'hard':
                    added_hard += 1
                    hard_count += 1
                else:
                    added_expert += 1
                    expert_count += 1

        flush_print(f"    +{added_hard} hard, +{added_expert} expert (totals: hard={hard_count}, expert={expert_count})")

        # Save progress
        with open(NEW_CARDS_FILE, 'w') as f:
            json.dump(new_cards, f, indent=2)

        time.sleep(0.5)

    # Summary
    flush_print(f"\n{'=' * 60}")
    flush_print(f"DONE! Generated {len(new_cards)} new cards")
    flush_print(f"  hard: {hard_count}")
    flush_print(f"  expert: {expert_count}")
    flush_print(f"\nSaved to: {NEW_CARDS_FILE}")


if __name__ == "__main__":
    main()

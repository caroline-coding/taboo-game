#!/usr/bin/env python3
"""Reclassify difficulty of new hard/expert cards."""

import anthropic
import json
import sys
import time

INPUT_FILE = "new_hard_expert_cards.json"
OUTPUT_FILE = "new_hard_expert_cards_reclassified.json"
BATCH_SIZE = 200


def flush_print(msg):
    print(msg)
    sys.stdout.flush()


def reclassify_batch(client, words):
    prompt = f"""I have a list of words used in a Taboo card game. Please classify each word's difficulty level based on how well-known it is to English speakers:

- "easy": Very common everyday words almost everyone knows (e.g., kitchen, birthday, summer, guitar)
- "medium": Common words most adults know (e.g., telescope, peninsula, metabolism, philanthropy)
- "hard": Words most college-educated adults would know but require some thought (e.g., paradox, oligarchy, metamorphosis, stoicism)
- "expert": Words only well-read or specialized people would know (e.g., solipsism, epistemology, hegemony, dialectic)

Words to classify:
{', '.join(words)}

Return ONLY a JSON object mapping each word to its difficulty (no other text):
{{"word1": "hard", "word2": "expert", ...}}"""

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
        return json.loads(text.strip())
    except Exception as e:
        flush_print(f"  Error: {e}")
        return {}


def main():
    with open(INPUT_FILE) as f:
        cards = json.load(f)
    flush_print(f"Cards to reclassify: {len(cards)}")

    client = anthropic.Anthropic()
    words = [c['word'] for c in cards]

    # Process in batches
    classifications = {}
    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        flush_print(f"  Batch {batch_num}: {len(batch)} words...")
        result = reclassify_batch(client, batch)
        classifications.update(result)
        flush_print(f"    Got {len(result)} classifications")
        time.sleep(0.5)

    # Apply reclassifications
    changed = 0
    for card in cards:
        w = card['word']
        if w in classifications:
            old = card.get('difficulty', 'unknown')
            new = classifications[w]
            if old != new:
                card['difficulty'] = new
                changed += 1
        # Also try lowercase
        elif w.lower() in {k.lower(): k for k in classifications}:
            for k, v in classifications.items():
                if k.lower() == w.lower():
                    old = card.get('difficulty', 'unknown')
                    if old != v:
                        card['difficulty'] = v
                        changed += 1
                    break

    flush_print(f"\nReclassified {changed} cards")

    # Count by difficulty
    counts = {}
    for c in cards:
        d = c.get('difficulty', 'unknown')
        counts[d] = counts.get(d, 0) + 1
    for d in ['easy', 'medium', 'hard', 'expert']:
        flush_print(f"  {d}: {counts.get(d, 0)}")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(cards, f, indent=2)
    flush_print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

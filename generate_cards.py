#!/usr/bin/env python3
"""
Generate Taboo cards using the Anthropic API.
Creates a diverse set of cards across different difficulty levels.
"""

import anthropic
import json
import os
import sys
import time

# Initialize client
client = anthropic.Anthropic()

# Output file
OUTPUT_FILE = "cards.json"

# Simplified categories - fewer but larger batches
CATEGORIES = [
    # Easy (40%) - ~1600 cards
    {"name": "Animals (pets, wild, marine, birds, insects)", "difficulty": "easy", "count": 200},
    {"name": "Food and Drinks (meals, ingredients, cuisines, beverages)", "difficulty": "easy", "count": 250},
    {"name": "Household items, furniture, appliances, and tools", "difficulty": "easy", "count": 200},
    {"name": "Clothing, accessories, and fashion items", "difficulty": "easy", "count": 150},
    {"name": "Sports, games, and recreational activities", "difficulty": "easy", "count": 200},
    {"name": "Vehicles, transportation, and travel", "difficulty": "easy", "count": 150},
    {"name": "Nature, weather, plants, and landscapes", "difficulty": "easy", "count": 200},
    {"name": "Buildings, places, and locations", "difficulty": "easy", "count": 150},
    {"name": "Body parts and health-related terms", "difficulty": "easy", "count": 100},

    # Medium (30%) - ~1200 cards
    {"name": "Occupations, jobs, and professions", "difficulty": "medium", "count": 200},
    {"name": "Hobbies, activities, and everyday actions", "difficulty": "medium", "count": 200},
    {"name": "Holidays, celebrations, and traditions", "difficulty": "medium", "count": 150},
    {"name": "Famous movies, TV shows, and entertainment", "difficulty": "medium", "count": 200},
    {"name": "Countries, cities, landmarks, and geography", "difficulty": "medium", "count": 200},
    {"name": "Technology, gadgets, and internet terms", "difficulty": "medium", "count": 150},
    {"name": "Music genres, instruments, and famous songs", "difficulty": "medium", "count": 100},

    # Hard (20%) - ~800 cards
    {"name": "Emotions, feelings, and mental states", "difficulty": "hard", "count": 150},
    {"name": "Abstract concepts and ideas", "difficulty": "hard", "count": 200},
    {"name": "Idioms, phrases, and expressions", "difficulty": "hard", "count": 200},
    {"name": "Personality traits and human characteristics", "difficulty": "hard", "count": 150},
    {"name": "Business, economics, and finance terms", "difficulty": "hard", "count": 100},

    # Expert (10%) - ~400 cards
    {"name": "Philosophy, ethics, and deep concepts", "difficulty": "expert", "count": 100},
    {"name": "Psychology and cognitive terms", "difficulty": "expert", "count": 100},
    {"name": "Scientific and technical concepts", "difficulty": "expert", "count": 100},
    {"name": "Literary devices, wordplay, and language tricks", "difficulty": "expert", "count": 100},
]

def flush_print(msg):
    """Print with immediate flush."""
    print(msg)
    sys.stdout.flush()

def generate_cards_batch(category, count, existing_words):
    """Generate a batch of cards for a category."""

    difficulty_guidance = {
        "easy": "These should be common, everyday words that most people know.",
        "medium": "These should be moderately challenging - known to most adults but requiring some thought.",
        "hard": "These should be challenging - abstract concepts, idioms, or things requiring creative clue-giving.",
        "expert": "These should be very challenging - technical terms, philosophical concepts, or words requiring sophisticated clues."
    }

    # Only include a sample of existing words to avoid prompt being too long
    sample_existing = list(existing_words)[:50] if existing_words else []

    prompt = f"""Generate exactly {count} unique Taboo cards for the category: {category['name']}

Difficulty level: {category['difficulty'].upper()}
{difficulty_guidance[category['difficulty']]}

For each card:
1. Target word: 1-3 words
2. Exactly 5 taboo words (the obvious clues people would give)

AVOID these already-used words: {', '.join(sample_existing) if sample_existing else 'none yet'}

Return ONLY a JSON array:
[{{"word": "Example", "taboo": ["word1", "word2", "word3", "word4", "word5"], "difficulty": "{category['difficulty']}"}}]"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        text = response.content[0].text.strip()
        # Handle potential markdown code blocks
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

def load_existing_cards():
    """Load existing cards if file exists."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            return json.load(f)
    return []

def save_cards(cards):
    """Save cards to file."""
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(cards, f, indent=2)

def main():
    flush_print("Taboo Card Generator")
    flush_print("=" * 50)

    # Load existing cards
    all_cards = load_existing_cards()
    existing_words = set(card['word'].lower() for card in all_cards)

    flush_print(f"Starting with {len(all_cards)} existing cards")

    # Calculate total
    total_target = sum(cat['count'] for cat in CATEGORIES)
    flush_print(f"Target: {total_target} cards across {len(CATEGORIES)} categories\n")

    # Track progress by category
    category_counts = {}
    for card in all_cards:
        cat = card.get('category', 'Unknown')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Generate cards for each category
    for category in CATEGORIES:
        current_count = category_counts.get(category['name'], 0)
        needed = category['count'] - current_count

        if needed <= 0:
            flush_print(f"[SKIP] {category['name']}: Already have {current_count}/{category['count']}")
            continue

        flush_print(f"[{category['difficulty'].upper()}] {category['name'][:40]}: {needed} cards...")

        # Generate in batches of 50
        batch_size = 50
        generated = 0
        zero_count = 0
        max_zero_batches = 3  # Move on if we get 3 batches with no new cards

        while generated < needed:
            batch_count = min(batch_size, needed - generated)
            cards = generate_cards_batch(category, batch_count, existing_words)

            # Add category and deduplicate
            new_cards = []
            for card in cards:
                word_lower = card['word'].lower()
                if word_lower not in existing_words:
                    card['category'] = category['name']
                    new_cards.append(card)
                    existing_words.add(word_lower)

            all_cards.extend(new_cards)
            generated += len(new_cards)

            # Save progress
            save_cards(all_cards)

            flush_print(f"  +{len(new_cards)} cards (total: {len(all_cards)})")

            # Track zero batches
            if len(new_cards) == 0:
                zero_count += 1
                if zero_count >= max_zero_batches:
                    flush_print(f"  Moving on (exhausted unique words)")
                    break
            else:
                zero_count = 0

            # Small delay to avoid rate limiting
            time.sleep(0.3)

        flush_print(f"  Done: {category['name'][:30]}\n")

    flush_print("=" * 50)
    flush_print(f"Complete! Total: {len(all_cards)} cards")

    # Print summary by difficulty
    difficulty_counts = {}
    for card in all_cards:
        d = card.get('difficulty', 'unknown')
        difficulty_counts[d] = difficulty_counts.get(d, 0) + 1

    flush_print("\nBy difficulty:")
    for d, count in sorted(difficulty_counts.items()):
        flush_print(f"  {d}: {count}")

    flush_print(f"\nSaved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

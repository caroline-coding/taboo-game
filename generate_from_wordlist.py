#!/usr/bin/env python3
"""
Generate Taboo cards from a word frequency list.
Uses the frequency list for word sourcing and the Anthropic API for taboo word generation.

Pipeline:
1. Download English word frequency list
2. Filter to good taboo candidates (remove function words, verb forms, names, etc.)
3. Split into difficulty tiers by frequency
4. Send batches to Anthropic API to select good cards and generate taboo words
5. Merge with existing cards
"""

import anthropic
import json
import os
import sys
import time
import urllib.request

FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt"
CARDS_FILE = "cards.json"
NEW_CARDS_FILE = "new_cards.json"

# Common first names to exclude (from subtitle frequency list)
FIRST_NAMES = {
    'james', 'john', 'robert', 'michael', 'david', 'richard', 'charles',
    'joseph', 'thomas', 'christopher', 'daniel', 'matthew', 'anthony',
    'mark', 'donald', 'steven', 'paul', 'andrew', 'joshua', 'kenneth',
    'kevin', 'brian', 'george', 'timothy', 'ronald', 'edward', 'jason',
    'jeffrey', 'ryan', 'jacob', 'gary', 'nicholas', 'eric', 'jonathan',
    'stephen', 'larry', 'justin', 'scott', 'brandon', 'benjamin', 'samuel',
    'raymond', 'gregory', 'frank', 'alexander', 'patrick', 'jack', 'dennis',
    'jerry', 'tyler', 'aaron', 'jose', 'adam', 'nathan', 'henry', 'peter',
    'mary', 'patricia', 'jennifer', 'linda', 'barbara', 'elizabeth',
    'susan', 'jessica', 'sarah', 'karen', 'lisa', 'nancy', 'betty',
    'margaret', 'sandra', 'ashley', 'dorothy', 'kimberly', 'emily',
    'donna', 'michelle', 'carol', 'amanda', 'melissa', 'deborah',
    'stephanie', 'rebecca', 'sharon', 'laura', 'cynthia', 'kathleen',
    'amy', 'angela', 'shirley', 'anna', 'brenda', 'pamela', 'emma',
    'nicole', 'helen', 'samantha', 'katherine', 'christine', 'debra',
    'rachel', 'carolyn', 'janet', 'catherine', 'maria', 'heather',
    'diane', 'ruth', 'julie', 'olivia', 'joyce', 'virginia',
    # Common nicknames and TV character names
    'mike', 'bob', 'bill', 'jim', 'joe', 'tom', 'steve', 'chris',
    'dan', 'matt', 'tony', 'dave', 'rick', 'nick', 'jeff', 'ben',
    'sam', 'alex', 'max', 'jake', 'luke', 'kate', 'jane', 'sue',
    'ann', 'jen', 'meg', 'kim', 'amy', 'ray', 'ted', 'fred',
    'carl', 'phil', 'alan', 'dean', 'doug', 'earl', 'gene', 'glen',
    'greg', 'hal', 'hank', 'harry', 'howard', 'ian', 'ivan',
    'jimmy', 'johnny', 'kenny', 'leo', 'lenny', 'lloyd', 'lou',
    'marty', 'mick', 'neil', 'norm', 'oscar', 'otto', 'pete',
    'ralph', 'roger', 'ron', 'roy', 'russ', 'sean', 'seth',
    'sid', 'stan', 'terry', 'todd', 'troy', 'vince', 'wade',
    'walt', 'wayne', 'will', 'woody', 'zach',
    'abby', 'becky', 'bonnie', 'carla', 'cindy', 'claire', 'dawn',
    'donna', 'edna', 'faye', 'gail', 'gloria', 'grace', 'holly',
    'irene', 'ivy', 'jean', 'jill', 'joan', 'judy', 'julia',
    'kelly', 'liz', 'lucy', 'lynn', 'maggie', 'martha', 'megan',
    'molly', 'nora', 'pam', 'penny', 'rita', 'rosa', 'rose',
    'ruby', 'sally', 'sara', 'tina', 'vera', 'wendy',
    # TV/movie character names that appear frequently in subtitles
    'ricky', 'joey', 'ross', 'chandler', 'phoebe', 'monica',
    'homer', 'bart', 'marge', 'lisa', 'sheldon', 'leonard',
    'dexter', 'walter', 'jesse', 'skyler', 'hank', 'saul',
    'arya', 'sansa', 'tyrion', 'cersei', 'jaime', 'daenerys',
    'derek', 'meredith', 'cristina', 'izzie', 'alex', 'george',
    'lily', 'marshall', 'barney', 'robin', 'ted',
}

# Function words and other words that don't make good taboo cards
STOPWORDS = {
    'the', 'and', 'that', 'have', 'for', 'not', 'with', 'you', 'this',
    'but', 'his', 'from', 'they', 'been', 'has', 'her', 'she', 'him',
    'had', 'its', 'who', 'will', 'more', 'when', 'can', 'said', 'there',
    'each', 'which', 'their', 'them', 'than', 'other', 'into', 'could',
    'may', 'did', 'these', 'some', 'would', 'make', 'like', 'time',
    'very', 'your', 'just', 'know', 'take', 'come', 'get', 'about',
    'was', 'were', 'are', 'been', 'being', 'also', 'how', 'our',
    'out', 'what', 'all', 'were', 'then', 'because', 'any', 'those',
    'well', 'back', 'going', 'way', 'over', 'too', 'here', 'where',
    'after', 'yes', 'does', 'got', 'let', 'why', 'see', 'say',
    'now', 'should', 'tell', 'think', 'went', 'want', 'really',
    'right', 'look', 'only', 'still', 'thing', 'things', 'much',
    'before', 'good', 'own', 'through', 'same', 'down', 'long',
    'off', 'put', 'even', 'made', 'sure', 'okay', 'something',
    'never', 'need', 'someone', 'every', 'little', 'always',
    'nothing', 'everything', 'anything', 'maybe', 'gonna', 'gotta',
    'lot', 'done', 'give', 'keep', 'help', 'thought', 'another',
    'though', 'enough', 'might', 'must', 'shall', 'most', 'such',
    'many', 'both', 'already', 'between', 'again', 'once', 'quite',
    'rather', 'upon', 'without', 'within', 'toward', 'towards',
    'whether', 'whose', 'whom', 'else', 'since', 'until', 'while',
    'during', 'along', 'against', 'among', 'throughout', 'despite',
    'beyond', 'above', 'below', 'behind', 'beside', 'besides',
    'however', 'therefore', 'otherwise', 'moreover', 'furthermore',
    'nevertheless', 'nonetheless', 'meanwhile', 'instead', 'indeed',
    'perhaps', 'actually', 'apparently', 'basically', 'certainly',
    'definitely', 'especially', 'essentially', 'eventually',
    'obviously', 'probably', 'seriously', 'simply', 'suddenly',
    'supposed', 'truly', 'absolutely', 'anymore', 'anyway',
    'couldn', 'didn', 'doesn', 'hadn', 'hasn', 'haven', 'isn',
    'mustn', 'shouldn', 'wasn', 'weren', 'won', 'wouldn', 'aren',
    'ain', 'shan', 'needn',
}


def flush_print(msg):
    print(msg)
    sys.stdout.flush()


def download_frequency_list():
    """Download and parse the frequency list."""
    flush_print("Downloading frequency list...")
    response = urllib.request.urlopen(FREQ_URL)
    lines = response.read().decode('utf-8').strip().split('\n')

    words = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 2:
            word, freq = parts[0], int(parts[1])
            words.append((word, freq))

    flush_print(f"  Downloaded {len(words)} words")
    return words


def filter_candidates(freq_words, existing_words):
    """Filter frequency list to good taboo candidates."""
    candidates = []

    for word, freq in freq_words:
        w = word.lower()

        # Skip short words
        if len(w) < 3:
            continue

        # Skip words with special characters
        if "'" in w or "-" in w or any(c.isdigit() for c in w):
            continue

        # Skip function words
        if w in STOPWORDS:
            continue

        # Skip common first names
        if w in FIRST_NAMES:
            continue

        # Skip words already in our deck
        if w in existing_words:
            continue

        # Skip likely verb past tenses (but keep some -ed adjectives)
        # Keep: married, haunted, wicked, sacred, beloved
        # Skip: walked, talked, opened, started
        if w.endswith('ed') and len(w) > 5:
            # Keep compound/interesting -ed words, skip simple past tenses
            root = w[:-2] if not w.endswith('ied') else w[:-3] + 'y'
            if root in STOPWORDS or len(root) <= 3:
                continue

        # Skip gerunds that are just verb forms (but keep activity nouns)
        # running, swimming, painting are fine; going, being, having are not
        if w.endswith('ing') and w[:-3] in STOPWORDS:
            continue

        # Skip -ly adverbs
        if w.endswith('ly') and len(w) > 5:
            continue

        candidates.append((word, freq))

    return candidates


def assign_difficulty_tier(candidates):
    """Split candidates into difficulty tiers based on frequency rank."""
    tiers = {
        'easy': [],      # most common words
        'medium': [],    # moderately common
        'hard': [],      # less common
        'expert': [],    # rare
    }

    for i, (word, freq) in enumerate(candidates):
        if i < 2000:
            tiers['easy'].append(word)
        elif i < 6000:
            tiers['medium'].append(word)
        elif i < 15000:
            tiers['hard'].append(word)
        else:
            tiers['expert'].append(word)

    return tiers


def generate_taboo_batch(client, words, difficulty, existing_words_sample):
    """Send a batch of words to the API, get back good taboo cards."""

    prompt = f"""I have a list of words from a frequency dictionary. I want to make Taboo cards from them.

For each word below, decide if it would make a GOOD Taboo card. A good Taboo word is:
- A concrete noun, well-known concept, activity, place, or thing
- Something most English speakers would recognize
- Something a person could describe without using obvious related words
- NOT a verb form, adverb, adjective, or function word
- NOT a person's first name or obscure proper noun

For each GOOD word, generate exactly 5 taboo words (the most obvious clues someone would give).
Capitalize the main word naturally (e.g., "Volcano" not "volcano").

Difficulty: {difficulty}

Words to evaluate:
{', '.join(words)}

IMPORTANT: Only include words that make genuinely good Taboo cards. It's fine to reject most words.
Do NOT include any of these existing words: {', '.join(list(existing_words_sample)[:80])}

Return ONLY a JSON array (no other text):
[{{"word": "Volcano", "taboo": ["lava", "eruption", "mountain", "ash", "magma"], "difficulty": "{difficulty}"}}]

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
    flush_print("Taboo Card Generator - Word Frequency Pipeline")
    flush_print("=" * 60)

    # Load existing cards
    with open(CARDS_FILE) as f:
        existing_cards = json.load(f)
    existing_words = set(c['word'].lower() for c in existing_cards)
    flush_print(f"Existing cards: {len(existing_cards)}")

    # Download and filter
    freq_words = download_frequency_list()
    candidates = filter_candidates(freq_words, existing_words)
    flush_print(f"Candidates after filtering: {len(candidates)}")

    # Assign difficulty tiers
    tiers = assign_difficulty_tier(candidates)
    for diff, words in tiers.items():
        flush_print(f"  {diff}: {len(words)} candidates")

    # Initialize API client
    client = anthropic.Anthropic()

    # Load progress file if it exists
    if os.path.exists(NEW_CARDS_FILE):
        with open(NEW_CARDS_FILE) as f:
            new_cards = json.load(f)
        flush_print(f"\nResuming with {len(new_cards)} previously generated cards")
    else:
        new_cards = []

    new_words = set(c['word'].lower() for c in new_cards)
    all_existing = existing_words | new_words

    # Process each difficulty tier
    batch_size = 150  # words per API call
    target_per_tier = {
        'easy': 300,
        'medium': 300,
        'hard': 200,
        'expert': 100,
    }

    for difficulty in ['easy', 'medium', 'hard', 'expert']:
        tier_words = tiers[difficulty]
        target = target_per_tier[difficulty]
        tier_generated = sum(1 for c in new_cards if c.get('difficulty') == difficulty)

        if tier_generated >= target:
            flush_print(f"\n[SKIP] {difficulty}: already have {tier_generated}/{target}")
            continue

        flush_print(f"\n{'=' * 60}")
        flush_print(f"Processing {difficulty.upper()} tier ({len(tier_words)} candidates, target: {target})")
        flush_print(f"{'=' * 60}")

        offset = 0
        while tier_generated < target and offset < len(tier_words):
            batch = tier_words[offset:offset + batch_size]
            offset += batch_size

            if not batch:
                break

            flush_print(f"  Batch {offset // batch_size}: {len(batch)} words...")
            cards = generate_taboo_batch(client, batch, difficulty, all_existing)

            # Deduplicate
            added = 0
            for card in cards:
                w = card['word'].lower()
                if w not in all_existing:
                    card['difficulty'] = difficulty  # ensure correct difficulty
                    new_cards.append(card)
                    all_existing.add(w)
                    added += 1

            tier_generated += added
            flush_print(f"    +{added} cards (tier total: {tier_generated}, overall: {len(new_cards)})")

            # Save progress
            with open(NEW_CARDS_FILE, 'w') as f:
                json.dump(new_cards, f, indent=2)

            time.sleep(0.5)  # rate limiting

        flush_print(f"  {difficulty} complete: {tier_generated} cards")

    # Summary
    flush_print(f"\n{'=' * 60}")
    flush_print(f"DONE! Generated {len(new_cards)} new cards")

    diff_counts = {}
    for c in new_cards:
        d = c.get('difficulty', 'unknown')
        diff_counts[d] = diff_counts.get(d, 0) + 1
    for d in ['easy', 'medium', 'hard', 'expert']:
        flush_print(f"  {d}: {diff_counts.get(d, 0)}")

    flush_print(f"\nNew cards saved to: {NEW_CARDS_FILE}")
    flush_print(f"To merge into main deck, run:")
    flush_print(f"  python3 merge_new_cards.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import sys
import math
import random
import os
import time
from collections import defaultdict, Counter
from functools import lru_cache

# ====== FILE LOADING FUNCTIONS ======

def load_words(filename="wordle words.txt"):
    """Load the list of valid wordle words from the file."""
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Extract words from the quotes in the file
            words = [word.strip('"') for word in content.split(',')]
            # Filter to ensure we only have 5-letter words
            words = [word for word in words if len(word) == 5]
            return words
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)

def load_frequency_list(filename, valid_words):
    """
    Load and filter a word frequency list for valid 5-letter Wordle words.
    Handles comments and different formats.
    """
    word_ranks = {}
    
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            rank = 1
            for line in f:
                # Skip empty lines and comments
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Extract the word (handle different formats)
                word = line.strip().lower()
                
                # Handle comma-separated or quoted entries
                if ',' in word:
                    word = word.split(',')[0].strip()
                if '"' in word:
                    word = word.strip('"')
                
                # Keep only valid 5-letter words
                if len(word) == 5 and word in valid_words:
                    word_ranks[word] = rank
                    rank += 1
    except Exception as e:
        print(f"Warning: Couldn't process frequency file {filename}: {e}")
        return {}
    
    return word_ranks

def get_frequency_rankings(all_words):
    """
    Get word frequency rankings from either a prefiltered file or by processing
    the original frequency list.
    """
    # First try to load the prefiltered file
    filtered_file = "filtered_frequency_list.txt"
    if os.path.exists(filtered_file):
        try:
            word_ranks = {}
            with open(filtered_file, 'r', encoding='utf-8', errors='ignore') as f:
                rank = 1
                for line in f:
                    word = line.strip()
                    if word and len(word) == 5 and word in all_words:
                        word_ranks[word] = rank
                        rank += 1
            
            if word_ranks:
                print(f"Using {len(word_ranks)} words from filtered frequency list")
                return word_ranks
        except Exception as e:
            print(f"Couldn't read filtered list: {e}")
    
    valid_words_set = set(all_words)
    frequency_list_file = "frequency_list.txt"
    if os.path.exists(frequency_list_file):
        word_ranks = load_frequency_list(frequency_list_file, valid_words_set)
        if word_ranks:
            print(f"Processed {len(word_ranks)} words from {frequency_list_file}")
            
            # Save filtered list for next time
            try:
                with open(filtered_file, 'w', encoding='utf-8') as f:
                    for word in word_ranks.keys():
                        f.write(f"{word}\n")
            except Exception as e:
                print(f"Couldn't save filtered list: {e}")
            
            return word_ranks
    
    print("No frequency data found. Using unweighted word selection.")
    return {}

# ====== WORDLE GAME LOGIC ======

@lru_cache(maxsize=1000000)
def evaluate_guess(guess, target):
    """
    Evaluate a guess against the target word and return the pattern.
    Returns a string of r (gray), y (yellow), g (green) characters.
    """
    result = ['r'] * 5
    
    # Count remaining letters in target (after marking greens)
    target_chars = Counter(target)
    
    # First pass: mark green (correct position)
    for i in range(5):
        if guess[i] == target[i]:
            result[i] = 'g'
            target_chars[guess[i]] -= 1
    
    # Second pass: mark yellow (correct letter, wrong position)
    for i in range(5):
        if result[i] == 'r' and guess[i] in target_chars and target_chars[guess[i]] > 0:
            result[i] = 'y'
            target_chars[guess[i]] -= 1
    
    return ''.join(result)

def filter_words(guess, pattern, possible_words):
    """Filter the list of possible words based on the guess and pattern."""
    return [word for word in possible_words if evaluate_guess(guess, word) == pattern]

def calculate_entropy(word, possible_words):
    """
    Calculate the entropy (information gain) for a word.
    Higher entropy means the word is expected to eliminate more possibilities.
    """
    pattern_counts = defaultdict(int)
    
    # Count how many remaining words would yield each possible pattern
    for possible_word in possible_words:
        pattern = evaluate_guess(word, possible_word)
        pattern_counts[pattern] += 1
    
    # Calculate entropy using the formula: -sum(p * log2(p))
    total_words = len(possible_words)
    entropy = 0
    for count in pattern_counts.values():
        probability = count / total_words
        entropy -= probability * math.log2(probability)
    
    return entropy

# ====== WORD SELECTION FUNCTIONS ======

def get_candidate_words(possible_words, all_words, excluded_words, force_possible):
    """Determine which words to consider based on strategy and constraints."""
    # Special case for only one possibility
    if len(possible_words) == 1:
        return possible_words[0], []

    # Determine which words to check
    if force_possible:
        words_to_check = possible_words
    else:
        words_to_check = all_words
    
    # Remove excluded words
    if excluded_words:
        words_to_check = [w for w in words_to_check if w not in excluded_words]
    
    return None, words_to_check

def calculate_word_entropy_scores(words_to_check, possible_words):
    """Calculate entropy scores for all candidate words."""
    word_scores = {}
    for i, word in enumerate(words_to_check):
        # Minimal progress indicator
        if i % 500 == 0 and i > 0:
            print(".", end="", flush=True)
            
        # Calculate entropy (information gain)
        entropy = calculate_entropy(word, possible_words)
        word_scores[word] = entropy
    
    return word_scores

def apply_bonuses_to_top_candidates(top_candidates, possible_words, word_ranks):
    """Apply frequency and other bonuses to the top candidate words."""
    max_rank = max(word_ranks.values()) if word_ranks else 1
    final_scores = []
    
    for word, base_score in top_candidates:
        final_score = base_score
        
        # Add frequency bonus if available
        if word_ranks and word in word_ranks:
            # Convert rank to 0-1 scale (1 = most common)
            frequency_score = 1 - (word_ranks[word] / max_rank)
            if len(possible_words) <= 20:
                final_score += frequency_score * 0.5
        
        # Add bonus for words that could be the answer
        if word in possible_words:
            # Bonus to prefer valid answers when scores are close
            final_score += base_score * 0.01
        
        final_scores.append((word, final_score))
        print(f" {word}:{base_score:.3f} -> {final_score:.3f}")
    
    return final_scores

def find_best_guess(possible_words, all_words, excluded_words, word_ranks, 
                   force_possible=False, top_candidates_count=10, display_scores_thresh=20):
    """
    Find the word with the highest expected information gain using a two-pass approach.
    """
    # Check for special cases (very few words)
    best_word, words_to_check = get_candidate_words(possible_words, all_words, excluded_words, force_possible)
    if best_word:
        return best_word
    
    # Limit top candidates to available words
    top_candidates_count = min(top_candidates_count, len(words_to_check))
    
    print("Calculating...", end="", flush=True)
    
    # First pass: Calculate basic entropy scores for all words
    word_scores = calculate_word_entropy_scores(words_to_check, possible_words)
    
    # Get the top N candidates by entropy score
    top_candidates = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)[:top_candidates_count]
    
    print("|", flush=True)
    
    # Second pass: Apply bonuses and detailed scoring to top candidates
    final_scores = apply_bonuses_to_top_candidates(top_candidates, possible_words, word_ranks)
    
    # Sort by final score and get the best word
    final_scores.sort(key=lambda x: x[1], reverse=True)
    best_word = final_scores[0][0]
    
    return best_word

# ====== MAIN GAME LOOP ======

def main():
    start_time = time.time()
    
    # Load words and frequency data
    all_words = load_words()
    print(f"Loaded {len(all_words)} words.")
    
    word_ranks = get_frequency_rankings(all_words)
    
    possible_words = all_words.copy()
    random.shuffle(possible_words)
    skipped_words = set()
    
    # Track game state for undo feature
    guess_history = []
    pattern_history = []
    possible_words_history = [possible_words.copy()]
    
    # Strategy settings
    print("\nSelect your strategy:")
    print("  1: Optimal (maximizes information gain)")
    print("  2: Always guess from possible answers")
    strategy = input("Choice [1-2, default=1]: ") or "1"
    always_guess_possible = (strategy == "2")
    
    # Threshold for automatically switching to guessing from possible words
    guess_from_possible_threshold = 4
    
    # Strong opening words based on entropy analysis
    first_guesses = [
        "slate", "crane", "trace", "slant", "crate",
        "carte", "salet", "trade", "roate", "raise",
        "soare", "stare", "react", "caret", "alert"
    ]
    
    # Main game loop
    guess_count = 0
    solved = False
    
    while not solved and guess_count < 6:
        guess_count += 1
        
        # Select word to guess
        if len(possible_words) == 1:
            # Only one possibility left
            guess = possible_words[0]
            print(f"\nGuess {guess_count}: {guess} (only possibility)")
        else:
            if guess_count == 1:
                # Use a strong first guess
                guess = random.choice(first_guesses)
                print(f"\nGuess {guess_count}: {guess}")
            else:
                # Decide whether to force guessing from possible words
                force_possible = always_guess_possible or len(possible_words) <= guess_from_possible_threshold
                
                guess = find_best_guess(
                    possible_words,
                    all_words,
                    skipped_words,
                    word_ranks,
                    force_possible
                )
                
                method = "from remaining options" if force_possible else "for max information"
                print(f"\nGuess {guess_count}: {guess} {method}")
        
        # Show possible words if few remain
        print(f"({len(possible_words)} possible words)")
        if len(possible_words) <= 10:
            print("Options:", possible_words)
        
        # Save state for undo feature
        guess_history.append(guess)
        possible_words_history.append(possible_words.copy())
        
        # Get feedback from player
        pattern = input("Pattern (r=gray, y=yellow, g=green) or 'skip'/'undo': ").lower()
        
        # Handle undo command
        if pattern == "undo":
            if len(guess_history) <= 1:
                print("Nothing to undo!")
                guess_count -= 1
                continue
            else:
                # Remove most recent state
                guess_history.pop()
                possible_words_history.pop()
                
                # Go back to previous state
                possible_words = possible_words_history[-1].copy()
                guess_count -= 2  # -2 because we'll increment at start of loop
                
                print(f"Undid last pattern. Back to guess: {guess_history[-1]}")
                continue
        
        # Handle skip command
        if pattern == "skip":
            print(f"Skipping {guess}.")
            
            # Remove the current word from consideration
            skipped_words.add(guess)
            if guess in possible_words:
                possible_words.remove(guess)
            
            # Revert state changes for this attempt
            guess_history.pop()
            possible_words_history.pop()
            
            guess_count -= 1
            continue
        
        # Check for win condition
        if pattern == "ggggg":
            print(f"\nSolved in {guess_count} guesses!")
            elapsed = time.time() - start_time
            print(f"Total time: {elapsed:.2f} seconds")
            solved = True
            break
        
        # Validate pattern format
        if len(pattern) != 5 or any(c not in "ryg" for c in pattern):
            print("Invalid pattern. Use only r, y, g and exactly 5 characters.")
            
            # Revert state changes for this attempt
            guess_history.pop()
            possible_words_history.pop()
            
            guess_count -= 1
            continue
        
        # Record pattern
        pattern_history.append(pattern)
        
        # Filter possible words based on the pattern
        new_possible_words = filter_words(guess, pattern, possible_words)
        
        if not new_possible_words:
            print("Error: No matching words. Check your pattern or use 'undo'.")
            
            # Revert state changes for this attempt
            guess_history.pop()
            possible_words_history.pop()
            
            guess_count -= 1
            continue
        
        possible_words = new_possible_words
    
    # Handle game end
    if not solved:
        if possible_words:
            print(f"\nCouldn't solve in 6 guesses. Answers might be: {possible_words}")
        else:
            print("\nNo words match all the patterns provided.")

if __name__ == "__main__":
    main()
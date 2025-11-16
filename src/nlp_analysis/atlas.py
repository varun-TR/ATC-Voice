#!/usr/bin/env python3
"""
Automatic cleaner for transcripts.json
This script continuously monitors and cleans the JSON file to:
1. Remove entries where "thank you", "thanks", or "thank" is a standalone word or repeated
2. Remove spam "subscribe" messages (e.g., "Thank you for watching! Please subscribe...")
3. Remove © symbols and any text following them
4. Remove repeated patterns (e.g., '? ? ? ?', 'uh uh uh')
5. Categorize communications and detect airline callsigns (like atlas.py)
6. Flag duplicates
7. Keep the file clean and neat at all times
"""

import json
import re
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import functions from postprocess.py (which has the categorization functions)
from postprocess import (
    categorize_communication,
    detect_callsign,
    flag_duplicates,
    load_unified_config,
    preprocess_transcript
)

# Load phonetic alphabet function (may not exist in postprocess.py)
try:
    from postprocess import load_phonetic_alphabet
except ImportError:
    def load_phonetic_alphabet(phonetic_path: Path) -> dict:
        """Load phonetic alphabet mapping."""
        with open(phonetic_path, "r", encoding="utf-8") as f:
            return json.load(f)


class TranscriptionCleaner(FileSystemEventHandler):
    """Automatically clean the transcription file."""
    
    def __init__(self, input_file_path: Path, output_file_path: Path, 
                 category_keywords: dict = None, airline_callsigns: dict = None, 
                 phonetic_dict: dict = None):
        self.input_file_path = input_file_path
        self.output_file_path = output_file_path
        self.category_keywords = category_keywords or {}
        self.airline_callsigns = airline_callsigns or {}
        self.phonetic_dict = phonetic_dict or {}
        self.is_cleaning = False  # Prevent recursive cleaning
        self.last_cleaned_time = 0
        self.min_clean_interval = 2  # Minimum seconds between cleanings
    
    def remove_repeated_patterns(self, text: str) -> str:
        """
        Remove repeated patterns where the same word or character appears multiple times.
        Examples:
        - "? ? ? ? ? ?" -> ""
        - "? ?" -> ""
        - "uh uh uh uh" -> ""
        - "the the the" -> ""
        """
        if not text:
            return text
        
        original_text = text
        
        # Pre-filter: Check for excessive repetition (garbage detection)
        word_list = text.lower().split()
        if len(word_list) > 20:  # Only check if text is long enough
            # Count common filler words
            uh_count = word_list.count('uh')
            the_count = word_list.count('the')
            bye_count = text.lower().count('bye')
            
            # If more than 50% of words are "uh" or "the", it's garbage
            if uh_count > len(word_list) * 0.5 or the_count > len(word_list) * 0.5:
                return ''
            
            # If "bye" appears more than 10 times, it's garbage
            if bye_count > 10:
                return ''
        
        # Check for dot/period spam (. . . or 。 。 。)
        dot_count = text.count('. .') + text.count('。')
        if dot_count > 20:  # If more than 20 spaced dots, it's garbage
            return ''
        
        # Check for excessive "subscribe" or "thank you for watching" spam
        if text.lower().count('subscribe') > 3 or text.lower().count('thank you for watching') > 3:
            return ''
        
        # Check for simple "? ?" patterns that are just noise (with any amount of whitespace)
        # Matches: "? ?", "?  ?", "?   ?", etc.
        text_stripped = text.strip()
        if re.match(r'^\s*\?\s+\?\s*$', text_stripped):
            return ''
        
        # Check for "? ?" with excessive whitespace (like "?  ?" with lots of spaces)
        # Remove all whitespace and check if it's just question marks
        text_no_space = re.sub(r'\s+', '', text_stripped)
        if len(text_no_space) <= 3 and text_no_space.count('?') == len(text_no_space):
            return ''
        
        # Pattern 1: If the entire text is just repeated single characters with spaces (like "? ? ?")
        # Check if text matches pattern of single char repeated with spaces
        if re.match(r'^(\S)\s+(?:\1\s*)*\1?$', text_stripped):
            return ''
        
        # Pattern 2: Remove repeated single characters/punctuation within text (2+ times)
        # Matches "? ?" or "? ? ?" anywhere in the text
        text = re.sub(r'(\S)\s+\1(?:\s+\1)*', '', text)

        # Pattern 2a: Explicitly remove spaced question-mark sequences (robust to mixed spacing)
        # e.g., "? ?", "?   ?   ?" -> ""
        text = re.sub(r'(?:\?\s+){1,}\?', '', text)
        # Also remove question marks with very long spaces
        text = re.sub(r'\?\s{10,}\?', '', text)

        # Pattern 2b: Remove hyphenated stutter of the same letter (e.g., "S-S-S-S-", case-insensitive)
        # Allows optional spaces around hyphens and an optional trailing hyphen
        text = re.sub(r'\b([A-Za-z])(?:\s*-\s*\1){2,}-?\b', '', text, flags=re.IGNORECASE)

        # Pattern 2c: Remove laughter strings (e.g., "hahaha", "ahahahaha", long repeats)
        text = re.sub(r'(?i)(?:ha|ah){3,}', '', text)
        text = re.sub(r'(?i)(?:heh){2,}', '', text)

        # Pattern 2d: Remove hyphen-dot noise like "-.." or "-...."
        text = re.sub(r'-\.{2,}', '', text)
        
        # Pattern 3: Remove repeated words (3 or more times)
        # Matches patterns like "uh uh uh" or "the the the"
        text = re.sub(r'\b(\w+)\s+\1\s+\1(?:\s+\1)*\b', '', text, flags=re.IGNORECASE)
        
        # Pattern 4: Remove sequences of the same character repeated multiple times (5+ times)
        # Matches patterns like "?????" or "....."
        text = re.sub(r'(.)\1{4,}', '', text)
        
        # Clean up any resulting multiple spaces (including very long spaces)
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if event.src_path == str(self.input_file_path):
            self.clean_file()
    
    def clean_file(self):
        """Clean the JSON file by removing invalid entries and cleaning text. Appends to output file."""
        # Prevent recursive cleaning and rate limit
        current_time = time.time()
        if self.is_cleaning or (current_time - self.last_cleaned_time) < self.min_clean_interval:
            return
        
        self.is_cleaning = True
        self.last_cleaned_time = current_time
        
        try:
            # Check if input file exists and is not empty
            if not self.input_file_path.exists() or self.input_file_path.stat().st_size == 0:
                return
            
            # Load existing cleaned data if output file exists
            existing_cleaned_items = []
            processed_chunk_numbers = set()
            output_data = {}
            
            if self.output_file_path.exists() and self.output_file_path.stat().st_size > 0:
                try:
                    with open(self.output_file_path, "r", encoding="utf-8") as f:
                        output_data = json.load(f)
                    existing_cleaned_items = output_data.get("items", [])
                    # Track which chunk_numbers have already been processed
                    processed_chunk_numbers = {item.get("chunk_number") for item in existing_cleaned_items if "chunk_number" in item}
                    
                    # Add missing fields (category, airline, duplicate_flag) to existing items if needed
                    if self.category_keywords or self.airline_callsigns:
                        updated_existing = 0
                        for item in existing_cleaned_items:
                            needs_update = False
                            if "category" not in item and self.category_keywords:
                                raw_text = item.get("raw_transcription", "")
                                item["category"] = categorize_communication(raw_text, self.category_keywords)
                                needs_update = True
                            if "airline" not in item and self.airline_callsigns:
                                raw_text = item.get("raw_transcription", "")
                                callsign = detect_callsign(raw_text, self.airline_callsigns, self.phonetic_dict)
                                item["airline"] = callsign if callsign else "Unknown"
                                needs_update = True
                            if "duplicate_flag" not in item:
                                item["duplicate_flag"] = False
                                needs_update = True
                            if needs_update:
                                updated_existing += 1
                        if updated_existing > 0:
                            print(f"📝 Updated {updated_existing} existing items with missing fields")
                except (json.JSONDecodeError, Exception) as e:
                    print(f"⚠️  Warning: Could not read existing cleaned file: {e}. Starting fresh.")
                    existing_cleaned_items = []
                    processed_chunk_numbers = set()
            
            # Load data from input file
            with open(self.input_file_path, "r", encoding="utf-8") as f:
                input_data = json.load(f)
            
            input_items = input_data.get("items", [])
            if not input_items:
                return
            
            # Filter to only process new items (not already in cleaned file)
            new_items = [item for item in input_items if item.get("chunk_number") not in processed_chunk_numbers]
            
            if not new_items:
                # No new items to process
                return
            
            original_count = len(new_items)
            
            # Clean and filter new items
            cleaned_new_items = []
            removed_count = 0
            cleaned_text_count = 0
            
            for item in new_items:
                raw_text = item.get("raw_transcription", "")
                
                if not raw_text or not raw_text.strip():
                    removed_count += 1
                    continue
                
                # Check for "thank" in specific cases (case insensitive)
                raw_text_lower = raw_text.lower().strip()
                
                # Remove if it's just a hyphen or multiple hyphens (including "- -" or "- - -")
                if re.match(r'^[-\s]+$', raw_text.strip()):
                    removed_count += 1
                    continue
                
                # Case 1: Check if entire text is just "thank you", "thanks", or "thank" (standalone)
                # Also check for variations with minimal content (just thank you with punctuation)
                stripped_text = raw_text_lower.strip('.,!? ')
                if stripped_text in ['thank you', 'thanks', 'thank', 'thank you very much', 'thanks very much', 'thank you so much', 
                                      'thank you for watching', 'thanks for watching', 'thank you for watching this video']:
                    removed_count += 1
                    continue
                
                # Case 1a: Remove if transcription is ONLY "thank you" with minimal words (≤4 words with thank/watching)
                # This catches cases like "thank you", "thank you.", "one thank you", "thank you very much", etc.
                word_count = len(raw_text_lower.split())
                if word_count <= 5 and ('thank' in raw_text_lower or 'watching' in raw_text_lower):
                    removed_count += 1
                    continue
                
                # Case 2: Check for repeated "thank" patterns
                # Matches: "thank thank", "thank you thank you", "thanks thanks", etc.
                if re.search(r'\b(thank(?:\s+you)?|thanks)\s+\1\b', raw_text_lower):
                    removed_count += 1
                    continue
                
                # Case 2a: Check for repeated phrases like "Thank you for your time" (3+ times)
                # This catches entries like "Thank you for your time. Thank you for your time. Thank you for your time..."
                thank_phrases = [
                    r'thank\s+you\s+for\s+your\s+time',
                    r'thank\s+you\s+very\s+much',
                    r'thanks\s+very\s+much',
                ]
                found_repeated_phrase = False
                for phrase in thank_phrases:
                    matches = len(re.findall(phrase, raw_text_lower))
                    if matches >= 3:
                        found_repeated_phrase = True
                        break
                if found_repeated_phrase:
                    removed_count += 1
                    continue
                
                # Case 3: Check for spam "subscribe" messages
                # Matches variations of "Thank you for watching! Please subscribe..."
                if 'subscribe' in raw_text_lower and 'thank' in raw_text_lower:
                    # Check for common spam patterns
                    spam_patterns = [
                        r'thank\s+you\s+for\s+watching.*subscribe',
                        r'subscribe.*channel.*for\s+more',
                        r'please\s+subscribe.*channel',
                    ]
                    if any(re.search(pattern, raw_text_lower) for pattern in spam_patterns):
                        removed_count += 1
                        continue
                
                # Case 3a: Check if text is mostly whitespace/question marks followed by copyright
                # Pattern: "? ?" with lots of spaces and "©" or "BF-WATCH"
                text_before_copyright = raw_text.split('©')[0] if '©' in raw_text else raw_text
                text_before_copyright = text_before_copyright.split('BF-WATCH')[0] if 'BF-WATCH' in raw_text else text_before_copyright
                # Remove all whitespace and check if it's mostly just question marks
                text_no_space = re.sub(r'\s+', '', text_before_copyright)
                if len(text_no_space) <= 5 and text_no_space.count('?') >= len(text_no_space) * 0.8:
                    # If it's mostly question marks with minimal content, remove it
                    removed_count += 1
                    continue
                
                # Clean the text: Remove © and everything after it
                original_text = raw_text
                if '©' in raw_text:
                    raw_text = raw_text.split('©')[0].strip()
                    cleaned_text_count += 1
                
                # Remove "BF-WATCH" and everything after it
                if 'BF-WATCH' in raw_text:
                    raw_text = raw_text.split('BF-WATCH')[0].strip()
                    cleaned_text_count += 1
                
                # Remove "Thank you for watching!" from the end of transcriptions
                # This cleans valid transcriptions that end with spam
                text_before_watching = raw_text
                raw_text = re.sub(r'\s*[Tt]hank\s+you\s+for\s+watching[!.]?\s*$', '', raw_text, flags=re.IGNORECASE)
                raw_text = re.sub(r'\s*[Tt]hanks\s+for\s+watching[!.]?\s*$', '', raw_text, flags=re.IGNORECASE)
                if raw_text != text_before_watching:
                    cleaned_text_count += 1
                
                # Remove repeated patterns
                text_before_pattern_removal = raw_text
                raw_text = self.remove_repeated_patterns(raw_text)
                if raw_text != text_before_pattern_removal:
                    cleaned_text_count += 1
                
                # Remove standalone 'bye' tokens (case-insensitive), optionally followed by punctuation
                text_before_bye = raw_text
                raw_text = re.sub(r'\bbye\b[.!?]?', '', raw_text, flags=re.IGNORECASE)
                if raw_text != text_before_bye:
                    cleaned_text_count += 1
                
                # Clean up extra whitespace (including very long spaces)
                raw_text = re.sub(r'\s{2,}', ' ', raw_text)  # Replace 2+ spaces with single space
                raw_text = re.sub(r'\s+', ' ', raw_text).strip()  # Final cleanup
                
                # Skip if empty after cleaning
                if not raw_text:
                    removed_count += 1
                    continue
                
                # Update the transcription
                if raw_text != original_text:
                    item["raw_transcription"] = raw_text
                
                # Add categorization and callsign detection (like atlas.py)
                if self.category_keywords:
                    category = categorize_communication(raw_text, self.category_keywords)
                    item["category"] = category
                else:
                    item["category"] = "General Communications"
                
                if self.airline_callsigns:
                    callsign = detect_callsign(raw_text, self.airline_callsigns, self.phonetic_dict)
                    item["airline"] = callsign if callsign else "Unknown"
                else:
                    item["airline"] = "Unknown"
                
                # Initialize duplicate_flag (will be set by flag_duplicates)
                item["duplicate_flag"] = False
                
                cleaned_new_items.append(item)
            
            # Append new cleaned items to existing ones
            all_cleaned_items = existing_cleaned_items + cleaned_new_items
            
            # Flag duplicates in ALL items (existing + new) together
            if all_cleaned_items:
                all_cleaned_items, duplicate_count = flag_duplicates(all_cleaned_items)
                if duplicate_count > 0:
                    print(f"🔍 Flagged {duplicate_count} duplicate items")
            
            # Prepare output data structure
            if not output_data:
                # If no existing output file, use input file structure as base
                output_data = {
                    "created_utc": input_data.get("created_utc", ""),
                    "model_used": input_data.get("model_used", ""),
                    "items": all_cleaned_items
                }
                # Preserve last_updated_utc if it exists in input
                if "last_updated_utc" in input_data:
                    output_data["last_updated_utc"] = input_data["last_updated_utc"]
            else:
                # Update existing output data
                output_data["items"] = all_cleaned_items
                # Update last_updated_utc from input if available
                if "last_updated_utc" in input_data:
                    output_data["last_updated_utc"] = input_data["last_updated_utc"]
            
            # Update metadata if it exists (for categorized_transcription_results.json format)
            if "metadata" in output_data:
                output_data["metadata"]["total_items"] = len(all_cleaned_items)
            
            # Write all cleaned data (existing + new) to output file
            with open(self.output_file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            if removed_count > 0 or cleaned_text_count > 0:
                print(f"🧹 Processed {original_count} new items: Removed {removed_count} invalid entries, cleaned {cleaned_text_count} texts.")
            if cleaned_new_items:
                print(f"📝 Added {len(cleaned_new_items)} new items. Total in cleaned file: {len(all_cleaned_items)}")
            print(f"💾 Saved to: {self.output_file_path}")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Cleaning error: {e}")
        finally:
            self.is_cleaning = False


def run_periodic_cleaning(input_file_path: Path, output_file_path: Path, 
                          category_keywords: dict, airline_callsigns: dict, 
                          phonetic_dict: dict, interval: int = 30):
    """Run periodic cleaning in addition to file monitoring."""
    cleaner = TranscriptionCleaner(input_file_path, output_file_path, 
                                   category_keywords, airline_callsigns, phonetic_dict)
    
    while True:
        try:
            time.sleep(interval)
            cleaner.clean_file()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Periodic cleaning error: {e}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("🧹 AUTOMATIC TRANSCRIPTION CLEANER")
    print("=" * 70)
    
    # Setup file paths
    base_dir = Path("/home/atc_voice/ATC-Voice")
    input_file_path = base_dir / "src" / "data" / "logs" / "transcripts" / "transcripts.json"
    output_file_path = base_dir / "src" / "data" / "logs" / "transcripts" / "cleaned_transcripts.json"
    config_dir = base_dir / "config"
    unified_config_path = config_dir / "final_aviation_ultimate_with_emergency.json"
    phonetic_path = config_dir / "phonetic_alphabet.json"
    
    if not input_file_path.exists():
        print(f"❌ File not found: {input_file_path}")
        sys.exit(1)
    
    print(f"📂 Reading from: {input_file_path}")
    print(f"📝 Writing to: {output_file_path}")
    
    # Load configuration files (like atlas.py)
    category_keywords = {}
    airline_callsigns = {}
    phonetic_dict = {}
    
    if unified_config_path.exists():
        print("📚 Loading unified configuration...")
        try:
            category_keywords, airline_callsigns = load_unified_config(unified_config_path)
            print(f"✅ Loaded {len(category_keywords)} categories and {len(airline_callsigns)} callsigns")
        except Exception as e:
            print(f"⚠️  Warning: Could not load unified config: {e}")
    else:
        print(f"⚠️  Warning: Unified config not found at {unified_config_path}")
    
    if phonetic_path.exists():
        try:
            phonetic_dict = load_phonetic_alphabet(phonetic_path)
            print(f"✅ Loaded {len(phonetic_dict)} phonetic mappings")
        except Exception as e:
            print(f"⚠️  Warning: Could not load phonetic alphabet: {e}")
    else:
        print(f"⚠️  Warning: Phonetic alphabet not found at {phonetic_path}")
    
    print()
    print("🔄 Auto-cleaner features:")
    print("   - Removes standalone 'thank you', 'thanks', 'thank' entries")
    print("   - Removes repeated 'thank' patterns (e.g., 'thank thank')")
    print("   - Removes spam 'subscribe' messages (e.g., 'Thank you for watching! Please subscribe...')")
    print("   - Removes © symbols and text after them")
    print("   - Removes repeated patterns (e.g., '? ? ? ?', 'uh uh uh')")
    print("   - Removes spaced question-mark sequences (e.g., '? ?', '?   ?')")
    print("   - Removes standalone 'bye' tokens")
    print("   - Removes hyphenated stutters (e.g., 'S-S-S-S-') and laughter strings ('hahaha')")
    print("   - Removes hyphen-dot noise (e.g., '-..')")
    print("   - Cleans up whitespace")
    if category_keywords:
        print("   - Categorizes communications (like atlas.py)")
    if airline_callsigns:
        print("   - Detects airline callsigns (like atlas.py)")
    print("   - Flags duplicates")
    print("   - Runs continuously")
    print()
    
    # Create cleaner with configs
    cleaner = TranscriptionCleaner(input_file_path, output_file_path, 
                                 category_keywords, airline_callsigns, phonetic_dict)
    
    # Initial clean
    print("🧹 Running initial clean...")
    cleaner.clean_file()
    
    # Set up file monitoring
    observer = Observer()
    observer.schedule(cleaner, path=str(input_file_path.parent), recursive=False)
    observer.start()
    
    print("✅ Auto-cleaner started!")
    print("Press Ctrl+C to stop")
    print("-" * 70)
    
    try:
        # Also run periodic cleaning as backup (every 30 seconds)
        while True:
            time.sleep(30)
            cleaner.clean_file()
    except KeyboardInterrupt:
        print("\n🛑 Stopping auto-cleaner...")
        observer.stop()
    
    observer.join()
    print("✅ Auto-cleaner stopped.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



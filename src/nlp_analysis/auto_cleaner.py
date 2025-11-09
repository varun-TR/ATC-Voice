#!/usr/bin/env python3
"""
Automatic cleaner for categorized_transcription_results.json
This script continuously monitors and cleans the JSON file to:
1. Remove entries where "thank you", "thanks", or "thank" is a standalone word or repeated
2. Remove spam "subscribe" messages (e.g., "Thank you for watching! Please subscribe...")
3. Remove © symbols and any text following them
4. Remove repeated patterns (e.g., '? ? ? ?', 'uh uh uh')
5. Keep the file clean and neat at all times
"""

import json
import re
import time
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class TranscriptionCleaner(FileSystemEventHandler):
    """Automatically clean the categorized transcription file."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
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
        
        # Pattern 1: If the entire text is just repeated single characters with spaces (like "? ? ?")
        # Check if text matches pattern of single char repeated with spaces
        if re.match(r'^(\S)\s+(?:\1\s*)*\1?$', text.strip()):
            return ''
        
        # Pattern 2: Remove repeated single characters/punctuation within text (2+ times)
        # Matches "? ?" or "? ? ?" anywhere in the text
        text = re.sub(r'(\S)\s+\1(?:\s+\1)*', '', text)

        # Pattern 2a: Explicitly remove spaced question-mark sequences (robust to mixed spacing)
        # e.g., "? ?", "?   ?   ?" -> ""
        text = re.sub(r'(?:\?\s+){1,}\?', '', text)

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
        
        # Clean up any resulting multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if event.src_path == str(self.file_path):
            self.clean_file()
    
    def clean_file(self):
        """Clean the JSON file by removing invalid entries and cleaning text."""
        # Prevent recursive cleaning and rate limit
        current_time = time.time()
        if self.is_cleaning or (current_time - self.last_cleaned_time) < self.min_clean_interval:
            return
        
        self.is_cleaning = True
        self.last_cleaned_time = current_time
        
        try:
            # Check if file exists and is not empty
            if not self.file_path.exists() or self.file_path.stat().st_size == 0:
                return
            
            # Load data
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", [])
            if not items:
                return
            
            original_count = len(items)
            
            # Clean and filter items
            cleaned_items = []
            removed_count = 0
            cleaned_text_count = 0
            
            for item in items:
                raw_text = item.get("raw_transcription", "")
                
                if not raw_text or not raw_text.strip():
                    removed_count += 1
                    continue
                
                # Check for "thank" in specific cases (case insensitive)
                raw_text_lower = raw_text.lower().strip()
                
                # Case 1: Check if entire text is just "thank you", "thanks", or "thank" (standalone)
                if raw_text_lower in ['thank you', 'thanks', 'thank', 'thank.', 'thanks.', 'thank you.']:
                    removed_count += 1
                    continue
                
                # Case 2: Check for repeated "thank" patterns
                # Matches: "thank thank", "thank you thank you", "thanks thanks", etc.
                if re.search(r'\b(thank(?:\s+you)?|thanks)\s+\1\b', raw_text_lower):
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
                
                # Clean the text: Remove © and everything after it
                original_text = raw_text
                if '©' in raw_text:
                    raw_text = raw_text.split('©')[0].strip()
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
                
                # Clean up extra whitespace
                raw_text = re.sub(r'\s+', ' ', raw_text).strip()
                
                # Skip if empty after cleaning
                if not raw_text:
                    removed_count += 1
                    continue
                
                # Update the transcription
                if raw_text != original_text:
                    item["raw_transcription"] = raw_text
                
                cleaned_items.append(item)
            
            # Only update if changes were made
            if removed_count > 0 or cleaned_text_count > 0:
                data["items"] = cleaned_items
                data["metadata"]["total_items"] = len(cleaned_items)
                
                # Write back to file
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"🧹 Auto-cleaned: Removed {removed_count} invalid entries, cleaned {cleaned_text_count} texts. Total: {len(cleaned_items)}")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Cleaning error: {e}")
        finally:
            self.is_cleaning = False


def run_periodic_cleaning(file_path: Path, interval: int = 30):
    """Run periodic cleaning in addition to file monitoring."""
    cleaner = TranscriptionCleaner(file_path)
    
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
    
    # Setup file path
    base_dir = Path("/home/atc_voice/ATC-Voice")
    file_path = base_dir / "src" / "data" / "logs" / "transcripts" / "categorized_transcription_results.json"
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    print(f"📂 Monitoring: {file_path}")
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
    print("   - Runs continuously")
    print()
    
    # Create cleaner
    cleaner = TranscriptionCleaner(file_path)
    
    # Initial clean
    print("🧹 Running initial clean...")
    cleaner.clean_file()
    
    # Set up file monitoring
    observer = Observer()
    observer.schedule(cleaner, path=str(file_path.parent), recursive=False)
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



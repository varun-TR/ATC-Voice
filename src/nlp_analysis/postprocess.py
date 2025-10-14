import json
import re
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
from difflib import SequenceMatcher
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# ----------------------------- Preprocessing ----------------------------- #
def preprocess_transcript(text: str) -> str:
    """Normalize transcript for consistent matching."""
    if not text or text.strip() == "":
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ----------------------------- Utilities ----------------------------- #
def similarity(a: str, b: str) -> float:
    """Return similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def generate_ngrams(words: List[str], n: int) -> List[str]:
    """Return contiguous n-word phrases."""
    if n <= 0 or n > len(words):
        return []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


# ------------------------------ Categorizer ------------------------------ #
def load_dictionaries(dict_path: Path) -> dict:
    """Load and normalize category keywords from JSON file."""
    with open(dict_path, "r", encoding="utf-8") as f:
        category_keywords = json.load(f)

    normalized = {}
    for cat, kws in category_keywords.items():
        kws_lower = [kw.lower() for kw in kws]
        normalized[cat] = sorted(kws_lower, key=lambda s: len(s.split()), reverse=True)

    return normalized


def load_callsigns(callsign_path: Path) -> dict:
    """Load airline callsigns JSON where each airline has multiple aliases."""
    with open(callsign_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Flatten into {alias_lower: airline_name}
    callsigns = {}
    for airline, aliases in data.items():
        for alias in aliases:
            callsigns[alias.lower()] = airline
    return callsigns


def detect_callsign(text: str, callsigns: dict) -> str:
    """Return the airline name if any of its aliases or codes appear in transcript."""
    if not text:
        return ""
    t = preprocess_transcript(text)

    for alias, airline in callsigns.items():
        if re.search(rf"\b{re.escape(alias.lower())}\b", t):
            return airline
    return "Unknown"


def categorize_communication(text: str, category_keywords: dict, fuzzy_threshold: float = 0.85) -> str:
    """Return communication category using fuzzy phrase matching."""
    if not text or text.strip() == "":
        return "Miscellaneous"

    t = preprocess_transcript(text)
    words = t.split()

    best_match: Tuple[str, float, str] = (None, 0.0, "")
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in t:
                return category.replace("_", " ").title()

            kw_words = keyword.split()
            n = len(kw_words)
            ngrams = generate_ngrams(words, n)

            for ng in ngrams:
                score = similarity(keyword, ng)
                if score > best_match[1]:
                    best_match = (category, score, keyword)
                if score >= fuzzy_threshold:
                    return category.replace("_", " ").title()

    if best_match[1] >= 0.75:
        return best_match[0].replace("_", " ").title()
    return "Miscellaneous"


# ------------------------------ Duplicate Detection ------------------------------ #
def flag_duplicates(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Flag duplicate/redundant raw transcriptions."""
    seen = {}
    duplicate_count = 0

    for item in items:
        raw_text = item.get("raw_transcription", "")
        normalized = preprocess_transcript(raw_text)

        if normalized in seen:
            item["duplicate_flag"] = True
            seen[normalized]["duplicate_flag"] = True  # Mark original too
            duplicate_count += 1
        else:
            item["duplicate_flag"] = False
            seen[normalized] = item

    return items, duplicate_count


# ------------------------------ Path Setup ------------------------------ #
def setup_paths():
    """Setup directory paths for VM environment."""
    # Base directory structure - use absolute path
    base_dir = Path("/home/atc_voice/ATC-Voice")
    
    # Dictionary files location
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Input/Output paths - corrected paths
    input_dir = base_dir / "src" / "data" / "logs" / "transcripts"
    output_dir = base_dir / "src" / "data" / "logs" / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    paths = {
        "category_dict": config_dir / "category_dict.json",
        "callsign": config_dir / "airline_callsign.json",
        "input": input_dir / "transcription_results.json",
        "output": output_dir / "categorized_transcription_results.json"
    }
    
    return paths


# ------------------------------ Append Mode Functions ------------------------------ #
def load_existing_categorized_data(output_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, int]]:
    """Load existing categorized data for append mode."""
    if not output_path.exists():
        return [], {}, {}
    
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        items = data.get("items", [])
        
        # Count existing categories and airlines
        counts = {}
        airline_counts = {}
        
        for item in items:
            category = item.get("category", "Miscellaneous")
            airline = item.get("airline", "Unknown")
            
            counts[category] = counts.get(category, 0) + 1
            airline_counts[airline] = airline_counts.get(airline, 0) + 1
        
        return items, counts, airline_counts
    except Exception as e:
        print(f"Warning: Could not load existing categorized data: {e}")
        return [], {}, {}


def get_processed_chunk_numbers(existing_items: List[Dict[str, Any]]) -> set:
    """Get set of already processed chunk numbers."""
    return {item.get("chunk_number") for item in existing_items if "chunk_number" in item}


def append_categorized_data(new_items: List[Dict[str, Any]], output_path: Path, 
                          existing_items: List[Dict[str, Any]], 
                          counts: Dict[str, int], airline_counts: Dict[str, int],
                          duplicate_count: int) -> None:
    """Append new categorized items to existing file."""
    all_items = existing_items + new_items
    
    # Only update counts for new items (existing counts are already correct)
    for item in new_items:
        category = item.get("category", "Miscellaneous")
        airline = item.get("airline", "Unknown")
        counts[category] = counts.get(category, 0) + 1
        airline_counts[airline] = airline_counts.get(airline, 0) + 1
    
    # Create output structure
    output = {
        "metadata": {
            "created_utc": existing_items[0].get("timestamp_utc", "") if existing_items else "",
            "last_updated_utc": new_items[-1].get("timestamp_utc", "") if new_items else "",
            "total_items": len(all_items),
            "duplicate_count": duplicate_count,
            "category_dict": str(output_path.parent.parent.parent.parent / "config" / "category_dict.json"),
            "callsign_dict": str(output_path.parent.parent.parent.parent / "config" / "airline_callsign.json")
        },
        "items": all_items
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


# ------------------------------ File Monitoring ------------------------------ #
class TranscriptionFileHandler(FileSystemEventHandler):
    """Handle file system events for transcription file."""
    
    def __init__(self, paths: dict, category_keywords: dict, airline_callsigns: dict):
        self.paths = paths
        self.category_keywords = category_keywords
        self.airline_callsigns = airline_callsigns
        self.last_processed_size = 0
        
        # Initialize with current file size
        if self.paths["input"].exists():
            self.last_processed_size = self.paths["input"].stat().st_size
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        if event.src_path == str(self.paths["input"]):
            self.process_new_transcripts()
    
    def process_new_transcripts(self):
        """Process only new transcripts since last run."""
        try:
            if not self.paths["input"].exists():
                return
            
            current_size = self.paths["input"].stat().st_size
            if current_size <= self.last_processed_size:
                return
            
            print(f"\n🔄 New transcripts detected! Processing...")
            
            # Load existing categorized data
            existing_items, counts, airline_counts = load_existing_categorized_data(self.paths["output"])
            processed_chunks = get_processed_chunk_numbers(existing_items)
            
            # Load new transcription data
            with open(self.paths["input"], "r", encoding="utf-8") as f:
                data = json.load(f)
            
            all_items = data.get("items", [])
            
            # Find new items (not yet processed)
            new_items = []
            for item in all_items:
                chunk_num = item.get("chunk_number")
                if chunk_num not in processed_chunks:
                    new_items.append(item)
            
            if not new_items:
                print("No new transcripts to process.")
                self.last_processed_size = current_size
                return
            
            print(f"Processing {len(new_items)} new transcripts...")
            
            # Process new items
            categorized_new_items = []
            for item in new_items:
                raw_text = item.get("raw_transcription", "")
                category = categorize_communication(raw_text, self.category_keywords)
                callsign = detect_callsign(raw_text, self.airline_callsigns)
                
                item["category"] = category
                item["airline"] = callsign if callsign else "Unknown"
                categorized_new_items.append(item)
            
            # Detect duplicates in new items
            categorized_new_items, duplicate_count = flag_duplicates(categorized_new_items)
            
            # Append to existing data
            append_categorized_data(categorized_new_items, self.paths["output"], 
                                  existing_items, counts, airline_counts, duplicate_count)
            
            print(f"✅ Processed {len(categorized_new_items)} new transcripts")
            print(f"📝 Total categorized items: {len(existing_items) + len(categorized_new_items)}")
            
            self.last_processed_size = current_size
            
        except Exception as e:
            print(f"❌ Error processing new transcripts: {e}")


# ------------------------------ Main Logic ------------------------------ #
def process_transcripts_once(paths: dict, category_keywords: dict, airline_callsigns: dict):
    """Process all transcripts once (initial run or manual processing)."""
    print("📖 Reading transcripts...\n")

    with open(paths['input'], "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    
    # Load existing categorized data for append mode
    existing_items, counts, airline_counts = load_existing_categorized_data(paths['output'])
    processed_chunks = get_processed_chunk_numbers(existing_items)
    
    # Find unprocessed items
    new_items = []
    for item in items:
        chunk_num = item.get("chunk_number")
        if chunk_num not in processed_chunks:
            new_items.append(item)
    
    if not new_items:
        print("✅ All transcripts already processed!")
        return
    
    print(f"Processing {len(new_items)} new transcripts...")
    
    categorized_items: List[Dict[str, Any]] = []
    
    for idx, item in enumerate(new_items, 1):
        if idx % 10 == 0:
            print(f"  Processed {idx}/{len(new_items)}...", end="\r")
        
        raw_text = item.get("raw_transcription", "")
        category = categorize_communication(raw_text, category_keywords)
        callsign = detect_callsign(raw_text, airline_callsigns)

        # Count category
        counts[category] = counts.get(category, 0) + 1

        # Count airline if detected
        airline_name = callsign if callsign else "Unknown"
        airline_counts[airline_name] = airline_counts.get(airline_name, 0) + 1

        item["category"] = category
        item["airline"] = airline_name
        categorized_items.append(item)
    
    print(f"  Processed {len(new_items)}/{len(new_items)} ✅")

    # Detect and flag duplicates
    print("\n🔍 Detecting duplicates...")
    categorized_items, duplicate_count = flag_duplicates(categorized_items)

    # Append to existing data
    append_categorized_data(categorized_items, paths['output'], 
                          existing_items, counts, airline_counts, duplicate_count)

    # ---- Print summaries ----
    # Calculate total counts for all items (existing + new)
    total_items = existing_items + categorized_items
    total_category_counts = {}
    total_airline_counts = {}
    
    for item in total_items:
        category = item.get("category", "Miscellaneous")
        airline = item.get("airline", "Unknown")
        total_category_counts[category] = total_category_counts.get(category, 0) + 1
        total_airline_counts[airline] = total_airline_counts.get(airline, 0) + 1
    
    print("\n" + "=" * 70)
    print("📊 SUMMARY OF CATEGORIES")
    print("=" * 70)
    for cat, cnt in sorted(total_category_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (cnt / len(total_items)) * 100
        print(f"{cat:<30} {cnt:>4} ({percentage:>5.1f}%)")

    print("\n" + "=" * 70)
    print("✈️  SUMMARY OF AIRLINES")
    print("=" * 70)
    for airline, cnt in sorted(total_airline_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (cnt / len(total_items)) * 100
        print(f"{airline:<30} {cnt:>4} ({percentage:>5.1f}%)")

    print("\n" + "=" * 70)
    print("🔁 DUPLICATE ANALYSIS")
    print("=" * 70)
    print(f"Repeated communications: {duplicate_count}")
    print(f"Unique communications: {len(total_items) - duplicate_count}")
    print(f"Total items processed: {len(total_items)}")
    print(f"Duplicate percentage: {(duplicate_count/len(total_items)*100):.1f}%")
    
    print("\n✅ Categorization complete!")
    print(f"📝 Results saved to: {paths['output']}")


def start_live_monitoring(paths: dict, category_keywords: dict, airline_callsigns: dict):
    """Start live monitoring of transcription file."""
    print("\n🔄 Starting live monitoring mode...")
    print(f"📁 Monitoring: {paths['input']}")
    print("Press Ctrl+C to stop monitoring")
    print("-" * 70)
    
    # Process any existing unprocessed transcripts first
    process_transcripts_once(paths, category_keywords, airline_callsigns)
    
    # Set up file monitoring
    event_handler = TranscriptionFileHandler(paths, category_keywords, airline_callsigns)
    observer = Observer()
    observer.schedule(event_handler, path=str(paths['input'].parent), recursive=False)
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping live monitoring...")
        observer.stop()
    
    observer.join()
    print("✅ Live monitoring stopped.")


def main(debug=False, live_mode=False):
    print("=" * 70)
    print("🏷️  ATC TRANSCRIPT CATEGORIZER")
    print("=" * 70)
    
    # Setup paths
    paths = setup_paths()
    
    # Verify required files exist
    missing_files = []
    for name, path in paths.items():
        if name in ["category_dict", "callsign", "input"]:
            if not path.exists():
                missing_files.append(f"{name}: {path}")
    
    if missing_files:
        print("\n❌ Missing required files:")
        for mf in missing_files:
            print(f"   - {mf}")
        print("\n📝 Please ensure these files exist:")
        print(f"   - {paths['category_dict']}")
        print(f"   - {paths['callsign']}")
        print(f"   - {paths['input']}")
        sys.exit(1)
    
    print(f"📂 Input file: {paths['input']}")
    print(f"📂 Output file: {paths['output']}")
    print(f"📚 Category dict: {paths['category_dict']}")
    print(f"✈️  Callsign dict: {paths['callsign']}")
    print()
    
    print("Loading dictionaries...")
    category_keywords = load_dictionaries(paths['category_dict'])
    airline_callsigns = load_callsigns(paths['callsign'])

    print(f"✅ Loaded {len(category_keywords)} categories and {len(airline_callsigns)} callsigns.")
    
    if live_mode:
        start_live_monitoring(paths, category_keywords, airline_callsigns)
    else:
        process_transcripts_once(paths, category_keywords, airline_callsigns)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ATC Transcript Categorizer")
    parser.add_argument("--live", action="store_true", help="Enable live monitoring mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    try:
        main(debug=args.debug, live_mode=args.live)
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
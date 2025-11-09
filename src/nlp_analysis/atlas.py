import json
import re
import sys
import time
import os
import string
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
    
    # Replace weird punctuation (e.g. \u3002 or ideographic full stop)
    text = text.replace("\u3002", ".").replace("。", ".")
    
    # Convert spoken numbers to digits
    text = convert_spoken_numbers(text)
    
    # Remove repeated single words
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)
    
    # Remove sequences of dots like ". . . . . ." → "."
    text = re.sub(r'(\.\s*){2,}', '. ', text)
    
    # Remove repeated short phrases like "thank you. thank you."
    text = re.sub(r'(\b[\w\s]{2,20}[.!?])(\s*\1){2,}', r'\1', text)
    
    # Remove excessive "thank you" repetition specifically
    text = re.sub(r'(thank you[.!?\s]*){2,}', 'thank you.', text)
    
    # Remove repeated numeric patterns (like "1 2 000 9" repeated)
    text = re.sub(r'(\b[\d\s]{2,}\b)( \1)+', r'\1', text)
    
    # Remove unwanted copyright or annotation text
    text = re.sub(r"©.*?(transcript|TV).*", "", text, flags=re.IGNORECASE)
    
    # Remove non-printable characters
    text = re.sub(r'[^\x20-\x7E]+', ' ', text)
    
    # Normalize extra spaces and punctuation spacing
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([.,!?])\s*", r"\1 ", text)
    text = text.strip()
    
    return text


def convert_spoken_numbers(text: str) -> str:
    """Convert spoken numbers to digits for better ATC communication processing."""
    # Dictionary mapping spoken numbers to digits
    number_map = {
        'zero': '0', 'oh': '0', 'o': '0',
        'one': '1', 'won': '1',
        'two': '2', 'too': '2',
        'three': '3', 'tree': '3',
        'four': '4', 'fore': '4',
        'five': '5', 'fife': '5',
        'six': '6',
        'seven': '7',
        'eight': '8', 'ate': '8',
        'nine': '9', 'niner': '9',
        'ten': '10',
        'eleven': '11',
        'twelve': '12',
        'thirteen': '13',
        'fourteen': '14',
        'fifteen': '15',
        'sixteen': '16',
        'seventeen': '17',
        'eighteen': '18',
        'nineteen': '19',
        'twenty': '20',
        'thirty': '30',
        'forty': '40',
        'fifty': '50',
        'sixty': '60',
        'seventy': '70',
        'eighty': '80',
        'ninety': '90',
        'hundred': '00',
        'thousand': '000'
    }
    
    # Words that should NOT be converted even if they sound like numbers
    # These are common ATC words that should remain as words
    preserve_words = {
        'to', 'for', 'at', 'on', 'in', 'of', 'the', 'a', 'an', 'and', 'or', 'but',
        'with', 'by', 'from', 'up', 'down', 'out', 'off', 'over', 'under', 'through',
        'contact', 'switch', 'change', 'monitor', 'handoff', 'go', 'call', 'report',
        'cleared', 'cleared', 'maintain', 'expect', 'cross', 'level', 'altitude',
        'heading', 'direct', 'vector', 'course', 'runway', 'frequency', 'tower',
        'approach', 'departure', 'ground', 'clearance', 'takeoff', 'landing',
        'arrival', 'final', 'weather', 'wind', 'visibility', 'ceiling', 'clouds',
        'traffic', 'aircraft', 'caution', 'wake', 'turbulence', 'heavy', 'light',
        'emergency', 'mayday', 'pan', 'medical', 'fuel', 'engine', 'fire', 'failure',
        'unable', 'comply', 'declare', 'lost', 'communications', 'radio', 'hydraulic',
        'descent', 'landing', 'situation', 'continue', 'temperature', 'dew', 'point',
        'pressure', 'altimeter', 'current', 'conditions', 'direction', 'speed',
        'precipitation', 'alert', 'conflict', 'information', 'line', 'wait', 'short',
        'centerline', 'closed', 'lights', 'condition', 'use', 'in', 'use'
    }
    
    # Split text into words
    words = text.split()
    converted_words = []
    
    for word in words:
        # Clean word of punctuation for matching
        clean_word = re.sub(r'[^a-z]', '', word.lower())
        
        # Only convert if it's in the number map AND not in preserve words
        if clean_word in number_map and clean_word not in preserve_words:
            # Replace with digit(s)
            converted_words.append(number_map[clean_word])
        else:
            # Keep original word
            converted_words.append(word)
    
    return ' '.join(converted_words)


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
def load_unified_config(config_path: Path) -> Tuple[dict, dict]:
    """Load unified configuration file with categories, keywords, and callsigns."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract category keywords
    category_keywords = {}
    for category_name, category_data in data.items():
        keywords = category_data.get("keywords", [])
        related_patterns = category_data.get("related_patterns", [])
        
        # Combine keywords and related patterns
        all_keywords = keywords + related_patterns
        kws_lower = [kw.lower() for kw in all_keywords]
        category_keywords[category_name] = sorted(kws_lower, key=lambda s: len(s.split()), reverse=True)
    
    # Extract airline callsigns from the first category (they're the same in all)
    # Flatten into {alias_lower: airline_name}
    callsigns = {}
    for category_name, category_data in data.items():
        airline_callsigns = category_data.get("airline_callsigns", {})
        for airline, aliases in airline_callsigns.items():
            for alias in aliases:
                callsigns[alias.lower()] = airline
        break  # Only need to process once since all categories have the same callsigns
    
    return category_keywords, callsigns


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


def load_phonetic_alphabet(phonetic_path: Path) -> dict:
    """Load phonetic alphabet mapping."""
    with open(phonetic_path, "r", encoding="utf-8") as f:
        return json.load(f)


def words_to_digits(word: str) -> str:
    """Convert spelled numbers to digits."""
    mapping = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "niner": "9", "fife": "5"
    }
    return mapping.get(word, word)


def normalize_numbers(tokens: List[str]) -> List[str]:
    """Convert spelled numbers in list of tokens to digits."""
    return [words_to_digits(tok) for tok in tokens]


def detect_callsign(text: str, callsigns: dict, phonetic_dict: dict = None) -> str:
    """Return the airline name or GA tail number if detected in transcript."""
    if not text:
        return "Unknown"
    
    t = preprocess_transcript(text)
    text_upper = text.upper()
    
    # --- General Aviation Tail Number Detection (check first) ---
    # Check for direct N-numbers (e.g., N5194, N2905X)
    direct_match = re.search(r"\bN\d{1,5}[A-Z]{0,2}\b", text_upper)
    if direct_match:
        return f"General Aviation ({direct_match.group(0)})"
    
    # Decode phonetic GA sequences like "November six seven alpha foxtrot"
    if phonetic_dict:
        # Look for "november" followed by up to 7 tokens (max tail: 5 digits + 2 letters)
        ga_match = re.search(r"\bnovember(?:\s+[\w]+){1,7}\b", t)
        if ga_match:
            phrase = ga_match.group(0)
            tokens = re.split(r"[\s\-]+", phrase.strip())
            tokens = normalize_numbers(tokens)
            
            tail = "N"
            digit_count = 0
            letter_count = 0
            
            for token in tokens[1:]:  # Skip "november"
                if token in phonetic_dict:
                    if digit_count == 0:  # Letters before digits are invalid
                        break
                    if letter_count >= 2:  # Max 2 letters
                        break
                    tail += phonetic_dict[token]
                    letter_count += 1
                elif token.isdigit():
                    if letter_count > 0:  # No digits after letters
                        break
                    # Can be multi-digit like "1234"
                    new_digit_count = digit_count + len(token)
                    if new_digit_count > 5:  # Max 5 digits total
                        break
                    tail += token
                    digit_count = new_digit_count
                elif len(token) == 1 and token.isalpha():
                    if digit_count == 0:  # Letters before digits are invalid
                        break
                    if letter_count >= 2:  # Max 2 letters
                        break
                    tail += token.upper()
                    letter_count += 1
                else:
                    # Stop at invalid token
                    break
            
            tail = re.sub(r"[^A-Z0-9]", "", tail)
            
            # FAA format validation: N + 1–5 digits + 0–2 letters
            if re.match(r"^N\d{1,5}[A-Z]{0,2}$", tail) and digit_count >= 1:
                return f"General Aviation ({tail})"
    
    # --- Commercial Airline Callsign Detection (after GA check) ---
    # Try exact matches with word boundaries
    for alias, airline in callsigns.items():
        if re.search(rf"\b{re.escape(alias.lower())}\b", t):
            # Handle ambiguous "delta" case
            if alias.lower() == "delta":
                # Skip if it's part of a GA phrase
                if re.search(r"\bnovember\b", t):
                    continue
                # If used with phonetic patterns, treat as GA
                if re.search(r"\bdelta (alpha|bravo|charlie|echo|foxtrot|golf|hotel|india|juliet|kilo|lima|mike|oscar|papa|quebec|romeo|sierra|tango|uniform|victor|whiskey|xray|yankee|zulu)\b", t):
                    continue
                # If followed by valid flight number, it's an airline
                if re.search(r"\bdelta (\d+|one|two|three|four|five|six|seven|eight|nine|zero)\b", t):
                    return airline
                continue
            
            return airline
    
    # Try substring matches for callsigns
    for alias, airline in callsigns.items():
        if alias.lower() in t:
            return airline
    
    return "Unknown"


def categorize_communication(text: str, category_keywords: dict, fuzzy_threshold: float = 0.75) -> str:
    """Return communication category using exact keyword matching (first match wins)."""
    if not text or text.strip() == "":
        return "General Communications"

    # Normalize transcript: lowercase and remove punctuation
    text_lower = preprocess_transcript(text).lower()
    # Remove punctuation for matching
    text_clean = text_lower.translate(str.maketrans('', '', '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'))

    # Helper: stricter emergency gating
    def _is_true_emergency(t: str) -> bool:
        # Strong positive patterns
        positive_patterns = [
            r"\bmayday\b",
            r"\bpan(?:\s+pan){1,2}\b",
            r"\bdeclaring (an )?emergency\b",
            r"\bmedical emergency\b",
            r"\bfuel emergency\b",
            r"\bsquawk(?:ing)?\s*7700\b",
            r"\bengine (?:failure|out)\b",
            r"\bsmoke (?:in|on)\b",
            r"\bfire (?:on board|in (?:cabin|cockpit))\b",
            r"\bpriority (?:landing|handling)\b",
            r"\bunabl[e]? to maintain altitude\b",
            r"\blost communications\b"
        ]
        for pat in positive_patterns:
            if re.search(pat, t):
                return True
        # If only the token 'emergency' appears, require supporting context
        if re.search(r"\bemergency\b", t):
            # Likely misrecognition cases: 'emergency' followed by numbers/flight-like tokens
            if re.search(r"\bemergency\s+[a-zA-Z]*\d+", t):
                return False
            # Greetings + 'emergency' without declarative verbs
            if re.search(r"\b(good (afternoon|morning|evening)\s+)?emergency\b", t) and not re.search(r"\b(declare|declaring|mayday|pan)\b", t):
                return False
            # Require at least one supporting keyword if 'emergency' is present
            if not re.search(r"\b(declare|declaring|request|need|medical|fuel|priority|mayday|pan|7700|squawk)\b", t):
                return False
            return True
        return False

    # Separate "Miscellaneous" from other categories to check it last
    other_categories = {k: v for k, v in category_keywords.items() if k.lower() != "miscellaneous"}
    misc_keywords = category_keywords.get("Miscellaneous", [])

    # Check specific categories first (not Miscellaneous)
    for category, keywords in other_categories.items():
        for keyword in keywords:
            # Clean keyword: lowercase and remove punctuation
            kw_clean = keyword.lower().translate(str.maketrans('', '', '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'))

            # Check if keyword appears in text
            if kw_clean in text_clean:
                # Harden emergency detection: avoid false positives on lone 'emergency'
                if category.lower() == "emergency declarations":
                    if not _is_true_emergency(text_lower):
                        continue  # skip emergency category if not strongly supported
                return category

    # Then check Miscellaneous category if it exists
    if misc_keywords:
        for keyword in misc_keywords:
            kw_clean = keyword.lower().translate(str.maketrans('', '', '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'))
            if kw_clean in text_clean:
                return "Miscellaneous"

    # Fallback if no keyword matches
    return "General Communications"


def _is_semantically_similar(keyword: str, phrase: str) -> bool:
    """Check if two phrases are semantically similar, not just character-wise similar."""
    kw_words = keyword.split()
    ph_words = phrase.split()
    
    # If both phrases contain numbers, they should be very similar to match
    kw_has_numbers = any(word.isdigit() for word in kw_words)
    ph_has_numbers = any(word.isdigit() for word in ph_words)
    
    if kw_has_numbers and ph_has_numbers:
        # For phrases with numbers, require exact word matches for numbers
        kw_numbers = [word for word in kw_words if word.isdigit()]
        ph_numbers = [word for word in ph_words if word.isdigit()]
        if kw_numbers != ph_numbers:
            return False
    
    # Check if the alphabetic words are similar
    kw_alpha = [word for word in kw_words if word.isalpha()]
    ph_alpha = [word for word in ph_words if word.isalpha()]
    
    if len(kw_alpha) != len(ph_alpha):
        return False
    
    # Check if each alphabetic word is similar
    for kw_word, ph_word in zip(kw_alpha, ph_alpha):
        if similarity(kw_word, ph_word) < 0.8:
            return False
    
    return True


# ------------------------------ Transcription Filtering ------------------------------ #
def is_valid_transcription(text: str) -> bool:
    """
    Check if a transcription is valid and should be included.
    Returns False if the text is:
    - Only dots/periods (Western: . or Japanese: 。)
    - Only "thank you" variations
    - Contains excessive repetitive dots and periods
    - Contains excessive Chinese/Japanese characters (often transcription artifacts)
    - Empty or whitespace only
    """
    if not text or not text.strip():
        return False
    
    # Clean the text - remove copyright notices
    if '©' in text:
        text = text.split('©')[0]
    
    text = text.strip()
    
    # Empty after cleaning
    if not text:
        return False
    
    # Pattern 1: Check for excessive dots/periods pattern (e.g., ". . . . ." or "。 。 。")
    # Remove spaces and check if mostly dots
    text_no_space = text.replace(' ', '').replace('\n', '').replace('\t', '')
    
    # Check if only dots/periods (both Western and Japanese)
    if all(c in '.。' for c in text_no_space):
        return False
    
    # Check if mostly dots (more than 70% dots/periods)
    dot_count = text_no_space.count('.') + text_no_space.count('。')
    if len(text_no_space) > 0 and dot_count > len(text_no_space) * 0.7:
        return False
    
    # Pattern 2: Check for repetitive dot patterns with spaces (e.g., ". . . . . . .")
    # Count sequences of dots separated by spaces
    dot_pattern = re.compile(r'[\.\。]\s*')
    dot_matches = dot_pattern.findall(text)
    if len(dot_matches) > 20:  # More than 20 dot sequences indicates invalid transcription
        return False
    
    # Pattern 3: Check if only "thank you" variations (case insensitive)
    text_lower = text.lower()
    # Remove punctuation for word analysis
    text_for_words = re.sub(r'[^\w\s]', '', text_lower)
    text_words = text_for_words.split()
    
    # Check if all words are only "thank", "you", "very", "much"
    if text_words and all(word in ['thank', 'you', 'very', 'much'] for word in text_words):
        return False
    
    # Pattern 4: Check for ANY occurrence of "thank you", "thanks", or standalone "thank"
    # Remove any transcription containing these gratitude expressions anywhere in the text
    if 'thank you' in text_lower or 'thanks' in text_lower or re.search(r'\bthank\b', text_lower):
        return False
    
    # Pattern 5: Check for excessive Chinese/Japanese characters (transcription artifacts)
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
    if chinese_chars > len(text) * 0.5:  # More than 50% Chinese/Japanese characters
        return False
    
    # Pattern 6: Check for lines that are almost entirely dots with a "thank you" at the end
    # Example: ". . . . . . . . . . 。 。 。 。 。 ... Thank you."
    if dot_count > 50 and len(text_words) <= 3:  # Many dots but very few actual words
        return False
    
    return True


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
        "unified_config": config_dir / "final_aviation_ultimate_with_emergency.json",
        "category_dict": config_dir / "category_dict.json",
        "callsign": config_dir / "airline_callsign.json",
        "phonetic": config_dir / "phonetic_alphabet.json",
        "input": input_dir / "transcripts.json",
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
            category = item.get("category", "General Communications")
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
        category = item.get("category", "General Communications")
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
            "unified_config": str(output_path.parent.parent.parent.parent / "config" / "final_aviation_ultimate_with_emergency.json")
        },
        "items": all_items
    }
    
    # Use atomic write to prevent corruption (write to temp file then rename)
    temp_path = output_path.with_suffix('.json.tmp')
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        # Atomic rename - this prevents partial writes from being read
        temp_path.replace(output_path)
    except Exception as e:
        # Clean up temp file if write failed
        if temp_path.exists():
            temp_path.unlink()
        raise e


# ------------------------------ File Monitoring ------------------------------ #
class TranscriptionFileHandler(FileSystemEventHandler):
    """Handle file system events for transcription file."""
    
    def __init__(self, paths: dict, category_keywords: dict, airline_callsigns: dict, phonetic_dict: dict = None):
        self.paths = paths
        self.category_keywords = category_keywords
        self.airline_callsigns = airline_callsigns
        self.phonetic_dict = phonetic_dict or {}
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
            print(f"📊 File size changed: {self.last_processed_size} → {current_size}")
            
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
                print("  No new transcripts to process")
                self.last_processed_size = current_size
                return
            
            print(f"  Found {len(new_items)} new transcripts to process")
            
            # Filter out invalid transcriptions and process valid items
            categorized_new_items = []
            filtered_count = 0
            
            for item in new_items:
                raw_text = item.get("raw_transcription", "")
                
                # Skip invalid transcriptions (only dots, thank you, etc.)
                if not is_valid_transcription(raw_text):
                    filtered_count += 1
                    continue
                
                category = categorize_communication(raw_text, self.category_keywords)
                callsign = detect_callsign(raw_text, self.airline_callsigns, self.phonetic_dict)
                
                item["category"] = category
                item["airline"] = callsign if callsign else "Unknown"
                categorized_new_items.append(item)
            
            if filtered_count > 0:
                print(f"  ⚠️  Filtered out {filtered_count} invalid transcriptions (dots, thank you, etc.)")
            
            # Detect duplicates in new items
            categorized_new_items, duplicate_count = flag_duplicates(categorized_new_items)
            
            # Append to existing data
            append_categorized_data(categorized_new_items, self.paths["output"], 
                                  existing_items, counts, airline_counts, duplicate_count)
            
            print(f"✅ Live processing complete! Added {len(categorized_new_items)} new items")
            print(f"📝 Total categorized items: {len(existing_items) + len(categorized_new_items)}")
            
            # Update last processed size
            self.last_processed_size = current_size
            
        except Exception as e:
            print(f"❌ Error in live processing: {e}")
            import traceback
            traceback.print_exc()


# ------------------------------ Main Logic ------------------------------ #
def process_transcripts_once(paths: dict, category_keywords: dict, airline_callsigns: dict, phonetic_dict: dict = None):
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
    filtered_count = 0
    
    for idx, item in enumerate(new_items, 1):
        if idx % 10 == 0:
            print(f"  Processed {idx}/{len(new_items)}...", end="\r")
        
        raw_text = item.get("raw_transcription", "")
        
        # Skip invalid transcriptions (only dots, thank you, etc.)
        if not is_valid_transcription(raw_text):
            filtered_count += 1
            continue
        
        category = categorize_communication(raw_text, category_keywords)
        callsign = detect_callsign(raw_text, airline_callsigns, phonetic_dict)

        # Count category
        counts[category] = counts.get(category, 0) + 1

        # Count airline if detected
        airline_name = callsign if callsign else "Unknown"
        airline_counts[airline_name] = airline_counts.get(airline_name, 0) + 1

        item["category"] = category
        item["airline"] = airline_name
        categorized_items.append(item)
    
    print(f"  Processed {len(new_items)}/{len(new_items)} ✅")
    
    if filtered_count > 0:
        print(f"  ⚠️  Filtered out {filtered_count} invalid transcriptions (dots, thank you, etc.)")

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
        category = item.get("category", "General Communications")
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


def start_live_monitoring(paths: dict, category_keywords: dict, airline_callsigns: dict, phonetic_dict: dict = None):
    """Start live monitoring of transcription file."""
    print("\n🔄 Starting live monitoring mode...")
    print(f"📁 Monitoring: {paths['input']}")
    print("Press Ctrl+C to stop monitoring")
    print("-" * 70)
    
    # Process any existing unprocessed transcripts first
    process_transcripts_once(paths, category_keywords, airline_callsigns, phonetic_dict)
    
    # Set up file monitoring
    event_handler = TranscriptionFileHandler(paths, category_keywords, airline_callsigns, phonetic_dict)
    observer = Observer()
    observer.schedule(event_handler, path=str(paths['input'].parent), recursive=False)
    
    observer.start()
    print("✅ File monitoring started")
    
    # Also set up periodic checking as backup
    last_check_time = time.time()
    check_interval = 5  # Check every 5 seconds as backup
    
    try:
        while True:
            time.sleep(1)
            
            # Periodic backup check in case file monitoring misses something
            current_time = time.time()
            if current_time - last_check_time >= check_interval:
                last_check_time = current_time
                event_handler.process_new_transcripts()
                
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
        if name in ["unified_config", "input"]:
            if not path.exists():
                missing_files.append(f"{name}: {path}")
    
    if missing_files:
        print("\n❌ Missing required files:")
        for mf in missing_files:
            print(f"   - {mf}")
        print("\n📝 Please ensure these files exist:")
        print(f"   - {paths['unified_config']}")
        print(f"   - {paths['input']}")
        sys.exit(1)
    
    print(f"📂 Input file: {paths['input']}")
    print(f"📂 Output file: {paths['output']}")
    print(f"📚 Unified config: {paths['unified_config']}")
    print()
    
    print("Loading unified configuration...")
    category_keywords, airline_callsigns = load_unified_config(paths['unified_config'])
    
    # Load phonetic alphabet for General Aviation detection
    phonetic_dict = {}
    if paths['phonetic'].exists():
        phonetic_dict = load_phonetic_alphabet(paths['phonetic'])
        print(f"✅ Loaded {len(category_keywords)} categories, {len(airline_callsigns)} callsigns, and {len(phonetic_dict)} phonetic mappings.")
    else:
        print(f"✅ Loaded {len(category_keywords)} categories and {len(airline_callsigns)} callsigns.")
        print("⚠️  Phonetic alphabet not found - General Aviation detection may be limited.")
    
    if live_mode:
        start_live_monitoring(paths, category_keywords, airline_callsigns, phonetic_dict)
    else:
        process_transcripts_once(paths, category_keywords, airline_callsigns, phonetic_dict)


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
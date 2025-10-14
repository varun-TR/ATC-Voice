import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from difflib import SequenceMatcher


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
    # Base directory structure
    base_dir = Path("ATC-Voice")
    
    # Dictionary files location
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Input/Output paths
    input_dir = base_dir / "src" / "data" / "logs" / "transcripts"
    output_dir = base_dir / "src" / "data" / "logs" / "categorized"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    paths = {
        "category_dict": config_dir / "category_dict.json",
        "callsign": config_dir / "airline_callsign.json",
        "input": input_dir / "transcription_results.json",
        "output": output_dir / "categorized_with_callsign.json"
    }
    
    return paths


# ------------------------------ Main Logic ------------------------------ #
def main(debug=False):
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
    print(f"📖 Reading transcripts...\n")

    with open(paths['input'], "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    categorized_items: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    airline_counts: Dict[str, int] = {}

    print(f"Processing {len(items)} transcripts...")
    for idx, item in enumerate(items, 1):
        if idx % 10 == 0:
            print(f"  Processed {idx}/{len(items)}...", end="\r")
        
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
    
    print(f"  Processed {len(items)}/{len(items)} ✅")

    # Detect and flag duplicates
    print("\n🔍 Detecting duplicates...")
    categorized_items, duplicate_count = flag_duplicates(categorized_items)

    # Add metadata to output
    output = {
        "metadata": {
            "created_utc": data.get("created_utc", ""),
            "last_updated_utc": data.get("last_updated_utc", ""),
            "total_items": len(categorized_items),
            "duplicate_count": duplicate_count,
            "category_dict": str(paths['category_dict']),
            "callsign_dict": str(paths['callsign'])
        },
        "items": categorized_items
    }

    print(f"💾 Saving categorized results to {paths['output']}...")
    with open(paths['output'], "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # ---- Print summaries ----
    print("\n" + "=" * 70)
    print("📊 SUMMARY OF CATEGORIES")
    print("=" * 70)
    for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (cnt / len(items)) * 100
        print(f"{cat:<30} {cnt:>4} ({percentage:>5.1f}%)")

    print("\n" + "=" * 70)
    print("✈️  SUMMARY OF AIRLINES")
    print("=" * 70)
    for airline, cnt in sorted(airline_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (cnt / len(items)) * 100
        print(f"{airline:<30} {cnt:>4} ({percentage:>5.1f}%)")

    print("\n" + "=" * 70)
    print("🔁 DUPLICATE ANALYSIS")
    print("=" * 70)
    print(f"Repeated communications: {duplicate_count}")
    print(f"Unique communications: {len(items) - duplicate_count}")
    print(f"Total items processed: {len(items)}")
    print(f"Duplicate percentage: {(duplicate_count/len(items)*100):.1f}%")
    
    print("\n✅ Categorization complete!")
    print(f"📝 Results saved to: {paths['output']}")


if __name__ == "__main__":
    try:
        main(debug=False)
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
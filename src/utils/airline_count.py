import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any
from difflib import get_close_matches


# ----------------------------- Utility Helpers ----------------------------- #
def words_to_digits(word: str) -> str:
    """Convert spelled numbers to digits."""
    mapping = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
    }
    return mapping.get(word, word)


def normalize_numbers(tokens: List[str]) -> List[str]:
    """Convert spelled numbers in list of tokens to digits."""
    return [words_to_digits(tok) for tok in tokens]


# ----------------------------- Preprocessing ----------------------------- #
def preprocess_transcript(text: str) -> str:
    """Normalize transcript for consistent matching."""
    if not text or text.strip() == "":
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ----------------------------- Loaders ----------------------------- #
def load_callsigns(callsign_path: Path) -> dict:
    with open(callsign_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    callsigns = {}
    for airline, aliases in data.items():
        for alias in aliases:
            callsigns[alias.lower()] = airline
    return callsigns


def load_phonetic_alphabet(phonetic_path: Path) -> dict:
    with open(phonetic_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------- Detection Logic ----------------------------- #
def detect_callsign(text: str, callsigns: Dict[str, str], phonetic_dict: Dict[str, str]) -> str:
    """Detect airline or general aviation callsign."""
    if not text:
        return "Unknown"

    t = preprocess_transcript(text)

    # ---  General Aviation Tail Number Detection ---
    # Check for direct N-numbers (e.g., N5194, N2905X)
    direct_match = re.search(r"\bN\d{1,5}[A-Z]{0,2}\b", text.upper())
    if direct_match:
        return f"General Aviation ({direct_match.group(0)})"

    # Decode phonetic GA sequences like “November six seven alpha foxtrot”
    ga_match = re.search(r"\bnovember[\s\-a-z0-9]+\b", t)
    if ga_match:
        phrase = ga_match.group(0)
        tokens = re.split(r"[\s\-]+", phrase.strip())
        tokens = normalize_numbers(tokens)

        tail = "N"
        for token in tokens[1:]:
            if token in phonetic_dict:
                tail += phonetic_dict[token]
            elif token.isdigit():
                tail += token
            elif len(token) == 1 and token.isalpha():
                tail += token.upper()

        tail = re.sub(r"[^A-Z0-9]", "", tail)

        # FAA format validation: N + 1–5 digits + 0–2 letters
        if re.match(r"^N\d{1,5}[A-Z]{0,2}$", tail):
            return f"General Aviation ({tail})"

    # --- ⃣ Airline Callsign Detection (after GA check) ---
    for alias, airline in callsigns.items():
        if re.search(rf"\b{re.escape(alias.lower())}\b", t):
            # --- Handle ambiguous cases like "delta" ---
            if alias.lower() == "delta":
                # Skip if it’s part of a GA phrase (e.g., November 23 Delta)
                if re.search(r"\bnovember\b", t):
                    continue

                # If "delta" is used with phonetic-like patterns, treat as GA
                if re.search(r"\bdelta (alpha|bravo|charlie|delta|echo|foxtrot|golf|hotel|india|juliet|kilo|lima|mike|november|oscar|papa|quebec|romeo|sierra|tango|uniform|victor|whiskey|xray|yankee|zulu)\b", t):
                    continue

                # If it's followed by a valid flight number (digits or spoken digits)
                if re.search(r"\bdelta (\d+|one|two|three|four|five|six|seven|eight|nine|zero)\b", t):
                    return airline

                # Otherwise, likely not an airline call
                continue

            # For all other aliases
            return airline


    return "Unknown"


# ----------------------------- Main Logic ----------------------------- #
def main(debug=False):
    base_dir = Path("/Users/anushadusakanti/PycharmProjects/690Project")

    callsign_path = base_dir / "airline_callsign.json"
    phonetic_path = base_dir / "phonetic_alphabet.json"

    input_path = "/Users/anushadusakanti/Downloads/transcripts.json"
    output_path = base_dir / "airlinecount.json"

    print("Loading dictionaries...")
    airline_callsigns = load_callsigns(callsign_path)
    phonetic_dict = load_phonetic_alphabet(phonetic_path)

    print(f"Loaded {len(airline_callsigns)} airline aliases and {len(phonetic_dict)} phonetic codes.")
    print(f"Reading transcripts from {input_path}...\n")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    airline_counts: Dict[str, int] = {}
    detected_items: List[Dict[str, Any]] = []

    for item in items:
        raw_text = item.get("raw_transcription", "")
        detected_airline = detect_callsign(raw_text, airline_callsigns, phonetic_dict)
        airline_counts[detected_airline] = airline_counts.get(detected_airline, 0) + 1
        item["airline"] = detected_airline
        detected_items.append(item)

    output = {"items": detected_items}

    print(f"Saving results to {output_path}...\n")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Summary of detected airlines:")
    for airline, cnt in sorted(airline_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{airline:<40} {cnt}")

    print(f"\nTotal communications processed: {len(items)}")


if __name__ == "__main__":
    try:
        main(debug=False)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

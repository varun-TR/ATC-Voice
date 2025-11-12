import json
import re
from pathlib import Path
from typing import Dict, List, Any

# ---------- Utility helpers ----------
def words_to_digits(word: str) -> str:
    mapping = {
        'zero': '0', 'oh': '0', 'o': '0',
        'one': '1', 'won': '1',
        'two': '2', 'too': '2',
        'three': '3', 'tree': '3',
        'four': '4', 'fore': '4',
        'five': '5', 'fife': '5',
        'six': '6',
        'seven': '7',
        'eight': '8', 'ate': '8',
        'nine': '9', 'niner': '9'
    }
    return mapping.get(word, word)

def combine_number_words(tokens: List[str]) -> List[str]:
    tens_map = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
    }
    result = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in tens_map and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if nxt in ["one","two","three","four","five","six","seven","eight","nine"]:
                num = tens_map[tok] + int(words_to_digits(nxt))
                result.append(str(num))
                i += 2
                continue
        result.append(tok)
        i += 1
    return result

def normalize_numbers(tokens: List[str]) -> List[str]:
    return [words_to_digits(tok) for tok in tokens]

def decode_phonetic_sequence(text: str, phonetic_dict: Dict[str, str]) -> str:
    tokens = re.split(r"[\s\-]+", text.lower().strip())
    tokens = combine_number_words(tokens)
    tokens = normalize_numbers(tokens)
    decoded = []
    for tok in tokens:
        if tok in phonetic_dict:
            decoded.append(phonetic_dict[tok].upper())
        elif tok.isdigit():
            decoded.append(tok)
        elif len(tok) == 1 and tok.isalpha():
            decoded.append(tok.upper())
    return " ".join(decoded)

def preprocess_transcript(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9\s\-]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- N-number validator ----------
def is_valid_ga_tail(tail: str) -> bool:
    if not tail or not tail.startswith("N"):
        return False
    tail = tail.upper()
    if len(tail) > 6:
        return False
    m = re.match(r"^N([1-9]\d{0,4})([A-HJ-NP-Z]{0,2})$", tail)
    if not m:
        return False
    n_digits = m.group(1)
    letters = m.group(2)
    if 1 <= int(n_digits) <= 99 and not letters:
        return False
    return True

# ---------- Flight detection ----------
def detect_callsign(text: str,
                    callsigns: Dict[str, list],
                    phonetic_dict: Dict[str, str],
                    nnumber_lookup: Dict[str, str]) -> str:
    if not text:
        return "Unknown"

    t = preprocess_transcript(text)
    tokens = re.split(r"[\s\-]+", t)
    tokens = combine_number_words(tokens)
    tokens = normalize_numbers(tokens)

    # --- 1️⃣ Airline / military alias detection ---
    decoded_flat = decode_phonetic_sequence(t, phonetic_dict)
    decoded_flat_clean = re.sub(r"[^A-Z0-9]", "", decoded_flat)
    for airline, aliases in callsigns.items():
        aliases = [aliases] if isinstance(aliases, str) else aliases
        for alias in aliases:
            alias_low = alias.lower()
            alias_up = alias.upper()
            if alias_low == "india" and not re.search(r"\bair\s+india\b", t):
                continue
            if alias_low == "delta":
                if re.search(r"\b(lufthansa|american|united|jetblue|british|air\s+canada|air\s+france)\b", t):
                    continue
                if re.search(
                        r"\bdelta (alpha|bravo|charlie|delta|echo|foxtrot|golf|hotel|india|juliet|kilo|lima|mike|november|oscar|papa|quebec|romeo|sierra|tango|uniform|victor|whiskey|xray|yankee|zulu)\b",
                        t):
                    continue
                if re.search(
                        r"\bdelta (\d+|one|two|three|four|five|six|seven|eight|nine|zero|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
                        t
                ):
                    return airline

                continue
            if alias_up in decoded_flat_clean or re.search(rf"\b{re.escape(alias_low)}\b", t):
                return airline

    # --- November-based N-number detection (FAA format) ---
    if "november" in t:
        after = re.split(r"\bnovember\b", t, maxsplit=1)[-1].strip()
        parts = re.split(r"[\s\-]+", after)
        tail_raw = "".join(
            [phonetic_dict.get(p, p).upper() if p in phonetic_dict else p for p in parts[:6]]
        )
        tail = "N" + re.sub(r"[^A-Z0-9]", "", tail_raw)

        # must contain both digits & letters
        if re.search(r"\d", tail) and re.search(r"[A-Z]", tail) and is_valid_ga_tail(tail):
            owner_name = nnumber_lookup.get(tail, "")
            if owner_name:
                return f"General Aviation ({tail})"
            else:
                return "Unknown"

    # --- No “November” → detect mixed digit-letter patterns---
    tail_tokens: List[str] = []
    for i, tok in enumerate(tokens + ["STOP"]):
        tok_low = tok.lower()
        if tok.isdigit() or tok_low in phonetic_dict:
            tail_tokens.append(tok)
        else:
            if tail_tokens:
                tail_raw = "".join(
                    [phonetic_dict.get(x.lower(), x).upper() if x.lower() in phonetic_dict else x.upper()
                     for x in tail_tokens]
                )
                tail_raw = re.sub(r"[^A-Z0-9]", "", tail_raw)
                # require at least one digit and one letter
                if not (re.search(r"\d", tail_raw) and re.search(r"[A-Z]", tail_raw)):
                    tail_tokens = []
                    continue
                tail = "N" + tail_raw
                if is_valid_ga_tail(tail):
                    owner_name = nnumber_lookup.get(tail, "")
                    if owner_name:
                        return f"General Aviation ({tail})"
                    else:
                        return "Unknown"
            tail_tokens = []


    return "Unknown"



# ---------- Main ----------
def main():
    base_dir = Path(".")
    callsign_path = base_dir / "airline_callsign.json"
    phonetic_path = base_dir / "phonetic_alphabet.json"
    nnumber_lookup_path = base_dir / "airline_nnumbers.json"
    input_path = base_dir / "new_transcription.json"
    output_path = base_dir / "airlinecount.json"

    print("Loading dictionaries...")
    callsigns = load_json(callsign_path)
    phonetic_dict = load_json(phonetic_path)
    nnumber_lookup = load_json(nnumber_lookup_path)

    print("Reading transcripts...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    counts, detected_items = {}, []

    for item in items:
        raw = item.get("raw_transcription", "")
        detected = detect_callsign(raw, callsigns, phonetic_dict, nnumber_lookup)
        ga_owner = None
        if detected.startswith("General Aviation"):
            match = re.search(r"\((N[0-9A-Z]+)\)", detected)
            if match:
                tail = match.group(1)
                owner = nnumber_lookup.get(tail)
                if owner:
                    if isinstance(owner, list):
                        owner = " ".join(owner)
                    ga_owner = str(owner)
        counts[detected] = counts.get(detected, 0) + 1
        item["airline"] = detected
        if ga_owner:
            item["registration_name"] = ga_owner
        detected_items.append(item)

    output = {"items": detected_items}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n--- Summary ---")
    for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{k:<35} {v}")
    print(f"\nTotal processed: {len(items)}")

if __name__ == "__main__":
    main()

"""
ATC Communication Categorization Script with Preprocessing (v2.1 — fixed paths)
==============================================================================

Per request: keep ALL logic the same as v2.1, only change how paths are provided:
- Input is always read from:  ATC-Voice/src/data/logs/transcripts/transcription_results.json
- Output is always written to: /home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json

CLI retains only non-path options:
    --limit <N>   Limit number of items processed
    --dry-run     Do not write output file (preview only)

Usage examples:
    python atc_categorizer_v2_1_fixed_paths.py
    python atc_categorizer_v2_1_fixed_paths.py --limit 50 --dry-run
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional


# ----------------------------- Preprocessing ----------------------------- #

def preprocess_transcript(text: str) -> str:
    """Normalize numbers & aviation terms to aid pattern matching.

    Examples:
        "flight level three two zero" -> "flight level 320"
        "climbing to two eight zero" -> "climbing to 280"
        "niner" -> "9"
    """
    if not text or text.strip() == "":
        return text

    text_lower = text.lower()

    # Aviation number word to digit mapping
    word_to_digit = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "niner": "9",
    }

    # 1) Convert "flight level" + number words -> digits (e.g., three two zero -> 320)
    def convert_flight_level(match: re.Match[str]) -> str:
        prefix = match.group(1)
        words = match.group(2).split()
        digits = "".join([word_to_digit.get(w, "") for w in words if w in word_to_digit])
        return f"{prefix}{digits}" if digits else match.group(0)

    text_lower = re.sub(
        r"(flight\s+level\s+)((?:\b(?:zero|one|two|three|four|five|six|seven|eight|nine|niner)\b\s*)+)",
        convert_flight_level,
        text_lower,
    )

    # 2) Convert sequences of 3+ consecutive number-words -> digits (e.g., two eight zero -> 280)
    # Note: keep it conservative (3 tokens) to avoid changing call signs like "two one".
    token = r"(zero|one|two|three|four|five|six|seven|eight|nine|niner)"
    pattern = rf"\b{token}\s+{token}\s+{token}\b"

    def replace_sequence(m: re.Match[str]) -> str:
        words = m.group(0).split()
        return "".join([word_to_digit.get(w, w) for w in words])

    text_lower = re.sub(pattern, replace_sequence, text_lower)

    return text_lower


# ------------------------------ Categorizer ------------------------------ #

def categorize_communication(text: str) -> str:
    """Categorize a single ATC utterance by priority patterns."""
    if not text or text.strip() == "":
        return "Miscellaneous"

    t = preprocess_transcript(text)

    # 1) Emergency
    emergency_patterns = [
        r"\bmayday\b",
        r"\bpan[-\s]?pan\b",
        r"\bemergency\b",
        r"\bdeclare\b.*\bemergency\b",
        r"\bfuel\b.*\bemergency\b",
    ]
    if any(re.search(p, t) for p in emergency_patterns):
        return "Emergency Declaration"

    # 2) Frequency Handoff (detect before altitudes)
    handoff_patterns = [
        r"\bcontact\s+\w+\s+(center|approach|tower|departure)\b",
        r"\b(center|approach|tower|departure)\s+\d{3}\.?\d*\b",
        r"\bfrequency\s+\d{3}\.?\d*\b",
        r"\bgood\s+(day|afternoon|morning|evening)\b",
        r"\bwith\s+you\b",
        r"\b\d{3}\.\d+\b",
        r"\bchecking\s+in\b",   # keeps routine sector check-ins as handoff
    ]

    if any(re.search(p, t) for p in handoff_patterns):
        return "Frequency Handoff"

    # 3) Altitude Clearance (avoid matching decimals like 121.85)
    altitude_patterns = [
        r"\bclimb(?:ing)?\b",
        r"\bdescend(?:ing)?\b",
        r"\bmaintain\b.*\b(altitude|flight\s+level)\b",
        r"\bflight\s+level\s+\d+\b",
        r"\bFL\s?\d{2,3}\b",                           # FL360 / FL 360
        r"\b\d{1,2},?\d{3}\s*(?:feet|ft)?\b",          # 17,000 / 28000 feet
        r"\bcleared\s+to\s+(?:climb|descend)\b",
        r"\bpassing\s+\d+(?:\.\d+)?\b",                # NEW: passing 23.5
        r"\blevel(?:ing)?\s+(?:at|for)?\s*\d+(?:\.\d+)?\b",  # NEW: leveling for 170 / 170.5
        r"\blevel\s+(?:is\s+)?\d+(?:\.\d+)?\b",        # "level is 170"
        r"\bfor\s+(?:FL\s?)?\d{2,3}\b",                # NEW: "... for 360" / "for FL360"
    ]

    if any(re.search(p, t) for p in altitude_patterns):
        return "Altitude Clearance"

    # 4) Heading Vector
    heading_patterns = [
        r"\bheading\s+\d{3}\b",
        r"\bturn\s+(left|right)\b",
        r"\bfly\s+heading\b",
        r"\bvector\b",
        r"\bdirect\s+\w+\b",
        r"\bproceed\s+direct\b",
    ]
    if any(re.search(p, t) for p in heading_patterns):
        return "Heading Vector"
    
        # Collapse digit triplets spoken as "3-8-0" or "3 8 0" -> "380"
    t = re.sub(r"\b(\d)\s*[-\s]\s*(\d)\s*[-\s]\s*(\d)\b", r"\1\2\3", t)

    # Normalize "27 and a half" -> "27.5"
    t = re.sub(r"\b(\d+)\s+and\s+a\s+half\b", r"\1.5", t)

    return "Miscellaneous"


# ------------------------------ I/O & CLI ------------------------------- #

@dataclass
class RunResult:
    total: int
    categories: Dict[str, int]
    output_file: Optional[Path]


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"Error: Input file not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Error: Invalid JSON in {path}: {e}")


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def find_latest_transcription_json(start_dirs: List[Path]) -> Optional[Path]:
    candidates: List[Path] = []
    for base in start_dirs:
        if not base.exists():
            continue
        candidates.extend(base.rglob("transcription_results.json"))
    if not candidates:
        return None
    # Choose the newest by mtime
    return max(candidates, key=lambda p: p.stat().st_mtime)


def process_transcriptions(input_path: Path, output_path: Optional[Path], limit: Optional[int] = None, dry_run: bool = False) -> RunResult:
    print("=" * 80)
    print("ATC COMMUNICATION CATEGORIZATION (WITH PREPROCESSING)")
    print("=" * 80)

    print(f"\nLoading data from {input_path}...")
    data = load_json(input_path)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise SystemExit("Error: JSON does not contain a list at key 'items'.")

    if limit is not None:
        items = items[:limit]

    print(f"Total communications loaded: {len(items)}")
    if len(items) == 0:
        return RunResult(total=0, categories={}, output_file=None)

    print("\nCategorizing communications...")
    categorized_items: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    for item in items:
        raw_text = item.get("raw_transcription", "")
        category = categorize_communication(raw_text)
        counts[category] = counts.get(category, 0) + 1

        categorized_items.append({
            "chunk_number": item.get("chunk_number"),
            "audio_file_raw": item.get("audio_file_raw"),
            "raw_duration_s": item.get("raw_duration_s"),
            "timestamp_utc": item.get("timestamp_utc"),
            "raw_transcription": raw_text,
            "category": category,
        })

    payload = {
        "created_utc": data.get("created_utc"),
        "items": categorized_items,
    }

    out_written: Optional[Path] = None
    if not dry_run and output_path is not None:
        print(f"\nSaving results to {output_path}...")
        save_json(output_path, payload)
        out_written = output_path
        print("✓ Output saved.")
    else:
        print("\n(dry-run) Not writing output file.")

    # Compact summary
    total = len(categorized_items)
    print("\n" + "=" * 80)
    print("CATEGORY DISTRIBUTION")
    print("=" * 80)
    print(f"{'Category':<30} {'Count':>8} {'Percentage':>12}")
    print("-" * 52)
    for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        pct = (cnt / total) * 100 if total else 0
        print(f"{cat:<30} {cnt:>8} {pct:>10.1f}%")
    print(f"{'TOTAL':<30} {total:>8} {100.0 if total else 0.0:>10.1f}%")

    return RunResult(total=total, categories=counts, output_file=out_written)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Categorize ATC communications with preprocessing"
    )
    # Keep only non-path options per request
    p.add_argument("--limit", type=int, default=None, help="Limit number of items for a quick run")
    p.add_argument("--dry-run", action="store_true", help="Do not write output file")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    # Fixed paths per request
    input_path = Path('ATC-Voice/src/data/logs/transcripts/transcription_results.json').expanduser().resolve()
    output_path = Path('/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json').expanduser().resolve()

    process_transcriptions(input_path=input_path, output_path=output_path, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

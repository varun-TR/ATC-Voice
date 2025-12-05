#!/usr/bin/env python3
"""Final comprehensive cleanup."""

import json
import re
from pathlib import Path

def should_remove(text: str) -> bool:
    """Check if entry should be removed."""
    if not text or not text.strip():
        return True
    
    # Remove hyphens only
    if re.match(r'^[-\s]+$', text.strip()):
        return True
    
    raw_text_lower = text.lower().strip()
    stripped_text = raw_text_lower.strip('.,!? ')
    
    # Remove standalone thank you messages
    if stripped_text in ['thank you', 'thanks', 'thank', 'thank you very much', 
                          'thanks very much', 'thank you so much', 
                          'thank you for watching', 'thanks for watching']:
        return True
    
    # Remove short entries with thank or watching
    word_count = len(raw_text_lower.split())
    if word_count <= 5 and ('thank' in raw_text_lower or 'watching' in raw_text_lower):
        return True
    
    return False

def main():
    file_path = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data.get("items", [])
    before = len(items)
    
    cleaned_items = [item for item in items if not should_remove(item.get("raw_transcription", ""))]
    
    data["items"] = cleaned_items
    data["metadata"]["total_items"] = len(cleaned_items)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Removed {before - len(cleaned_items)} entries")
    print(f"📊 Kept {len(cleaned_items)} entries")

if __name__ == "__main__":
    main()













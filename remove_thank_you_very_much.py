#!/usr/bin/env python3
"""Remove entries that are just 'thank you very much' or similar short thank you phrases."""

import json
from pathlib import Path

def clean_data():
    file_path = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print("🧹 Removing 'thank you very much' entries...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data.get("items", [])
    original_count = len(items)
    
    cleaned_items = []
    removed_count = 0
    
    for item in items:
        raw_text = item.get("raw_transcription", "")
        
        if not raw_text or not raw_text.strip():
            removed_count += 1
            continue
        
        raw_text_lower = raw_text.lower()
        stripped_text = raw_text_lower.strip('.,!? ')
        
        # Remove exact matches
        if stripped_text in ['thank you very much', 'thanks very much', 'thank you so much']:
            removed_count += 1
            continue
        
        # Remove short entries (4 words or less) with "thank"
        word_count = len(raw_text_lower.split())
        if word_count <= 4 and 'thank' in raw_text_lower:
            removed_count += 1
            continue
        
        cleaned_items.append(item)
    
    data["items"] = cleaned_items
    data["metadata"]["total_items"] = len(cleaned_items)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Removed {removed_count} entries")
    print(f"   Kept: {len(cleaned_items)} valid entries")

if __name__ == "__main__":
    clean_data()


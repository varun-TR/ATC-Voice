#!/usr/bin/env python3
"""
One-time cleanup script to remove invalid transcriptions from existing data.
Removes:
- Entries with just hyphens ("-", "--", "---", etc.)
- Entries containing "thank you" anywhere in the text
"""

import json
from pathlib import Path

def clean_existing_data():
    file_path = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print("🧹 Starting one-time cleanup of existing data...")
    print(f"📄 File: {file_path}")
    
    # Load data
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data.get("items", [])
    original_count = len(items)
    
    print(f"📊 Original count: {original_count:,} items")
    
    # Clean and filter items
    cleaned_items = []
    removed_count = 0
    
    for item in items:
        raw_text = item.get("raw_transcription", "")
        
        if not raw_text or not raw_text.strip():
            removed_count += 1
            continue
        
        # Remove if it's just hyphens
        if all(c in '-' for c in raw_text.strip()):
            removed_count += 1
            continue
        
        # Remove if transcription is ONLY "thank you" or very short with "thank"
        raw_text_lower = raw_text.lower()
        stripped_text = raw_text_lower.strip('.,!? ')
        
        # Case 1: Entire text is just "thank you"
        if stripped_text in ['thank you', 'thanks', 'thank']:
            removed_count += 1
            continue
        
        # Case 2: Very short transcription (3 words or less) containing "thank"
        word_count = len(raw_text_lower.split())
        if word_count <= 3 and 'thank' in raw_text_lower:
            removed_count += 1
            continue
        
        # Keep this item
        cleaned_items.append(item)
    
    # Update metadata
    data["items"] = cleaned_items
    data["metadata"]["total_items"] = len(cleaned_items)
    
    # Write back to file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Cleanup complete!")
    print(f"   Removed: {removed_count:,} invalid entries")
    print(f"   Kept: {len(cleaned_items):,} valid entries")
    print(f"   Reduction: {(removed_count/original_count*100):.1f}%")

if __name__ == "__main__":
    clean_existing_data()


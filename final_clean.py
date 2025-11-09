#!/usr/bin/env python3
import json
import re
from pathlib import Path

path = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")

print("🧹 Cleaning categorized_transcription_results.json...")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

original_count = len(data["items"])
print(f"Original: {original_count} items")

# Filter out entries with "thank" in any form
cleaned_items = []
removed_count = 0

for item in data["items"]:
    raw_text = item.get("raw_transcription", "").lower()
    if "thank you" in raw_text or "thanks" in raw_text or re.search(r'\bthank\b', raw_text):
        removed_count += 1
    else:
        cleaned_items.append(item)

data["items"] = cleaned_items
data["metadata"]["total_items"] = len(cleaned_items)

# Save
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Removed: {removed_count} entries")
print(f"✅ Remaining: {len(cleaned_items)} items")






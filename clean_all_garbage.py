#!/usr/bin/env python3
"""Comprehensive cleanup of all garbage entries from categorized transcriptions."""

import json
import re
from pathlib import Path

def is_garbage(text: str) -> bool:
    """Determine if text is garbage that should be removed."""
    if not text or not text.strip():
        return True
    
    # Remove if just hyphens and/or spaces
    if re.match(r'^[-\s]+$', text.strip()):
        return True
    
    raw_text_lower = text.lower()
    word_list = raw_text_lower.split()
    
    # Check for excessive repetition
    if len(word_list) > 20:
        uh_count = word_list.count('uh')
        the_count = word_list.count('the')
        bye_count = raw_text_lower.count('bye')
        
        # If more than 50% are filler words, it's garbage
        if uh_count > len(word_list) * 0.5 or the_count > len(word_list) * 0.5:
            return True
        
        if bye_count > 10:
            return True
    
    # Check for subscribe spam
    if raw_text_lower.count('subscribe') > 3 or raw_text_lower.count('thank you for watching') > 3:
        return True
    
    # Check for copyright/transcript spam
    if 'transcript emily beynon' in raw_text_lower or '© transcript' in raw_text_lower:
        return True
    
    # Remove short thank you messages
    stripped_text = raw_text_lower.strip('.,!? ')
    if stripped_text in ['thank you', 'thanks', 'thank', 'thank you very much', 'thanks very much', 'thank you so much']:
        return True
    
    # Remove very short with "thank" (4 words or less)
    if len(word_list) <= 4 and 'thank' in raw_text_lower:
        return True
    
    # Check for extremely long whitespace patterns (likely garbage)
    if '  ' * 50 in text:  # 100+ consecutive spaces
        return True
    
    # Check if it's just repeated question marks with spaces
    if re.match(r'^\s*\?\s+\?\s*', text.strip()) and text.count('?') > 2:
        return True
    
    return False

def clean_data():
    file_path = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print("🧹 Starting comprehensive garbage cleanup...")
    print("")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data.get("items", [])
    original_count = len(items)
    
    print(f"📊 Original count: {original_count} entries")
    print("")
    
    cleaned_items = []
    removed_count = 0
    removed_categories = {
        'hyphens': 0,
        'uh_spam': 0,
        'the_spam': 0,
        'bye_spam': 0,
        'subscribe_spam': 0,
        'thank_you': 0,
        'question_marks': 0,
        'whitespace': 0,
        'other': 0
    }
    
    for item in items:
        raw_text = item.get("raw_transcription", "")
        
        if not raw_text or not raw_text.strip():
            removed_count += 1
            removed_categories['other'] += 1
            continue
        
        # Categorize what type of garbage it is
        if re.match(r'^[-\s]+$', raw_text.strip()):
            removed_count += 1
            removed_categories['hyphens'] += 1
            continue
        
        raw_text_lower = raw_text.lower()
        word_list = raw_text_lower.split()
        
        if len(word_list) > 20:
            uh_count = word_list.count('uh')
            the_count = word_list.count('the')
            bye_count = raw_text_lower.count('bye')
            
            if uh_count > len(word_list) * 0.5:
                removed_count += 1
                removed_categories['uh_spam'] += 1
                continue
            
            if the_count > len(word_list) * 0.5:
                removed_count += 1
                removed_categories['the_spam'] += 1
                continue
            
            if bye_count > 10:
                removed_count += 1
                removed_categories['bye_spam'] += 1
                continue
        
        if raw_text_lower.count('subscribe') > 3 or raw_text_lower.count('thank you for watching') > 3:
            removed_count += 1
            removed_categories['subscribe_spam'] += 1
            continue
        
        if 'transcript emily beynon' in raw_text_lower or '© transcript' in raw_text_lower:
            removed_count += 1
            removed_categories['subscribe_spam'] += 1
            continue
        
        stripped_text = raw_text_lower.strip('.,!? ')
        if stripped_text in ['thank you', 'thanks', 'thank', 'thank you very much', 'thanks very much', 'thank you so much']:
            removed_count += 1
            removed_categories['thank_you'] += 1
            continue
        
        if len(word_list) <= 4 and 'thank' in raw_text_lower:
            removed_count += 1
            removed_categories['thank_you'] += 1
            continue
        
        if '  ' * 50 in raw_text:
            removed_count += 1
            removed_categories['whitespace'] += 1
            continue
        
        if re.match(r'^\s*\?\s+\?\s*', raw_text.strip()) and raw_text.count('?') > 2:
            removed_count += 1
            removed_categories['question_marks'] += 1
            continue
        
        # Keep this item
        cleaned_items.append(item)
    
    data["items"] = cleaned_items
    data["metadata"]["total_items"] = len(cleaned_items)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("✅ Cleanup complete!")
    print("")
    print("📉 Removed entries by category:")
    print(f"   Hyphens/spaces only: {removed_categories['hyphens']}")
    print(f"   'uh' spam: {removed_categories['uh_spam']}")
    print(f"   'the' spam: {removed_categories['the_spam']}")
    print(f"   'bye' spam: {removed_categories['bye_spam']}")
    print(f"   Subscribe/watching spam: {removed_categories['subscribe_spam']}")
    print(f"   Thank you messages: {removed_categories['thank_you']}")
    print(f"   Question mark spam: {removed_categories['question_marks']}")
    print(f"   Whitespace garbage: {removed_categories['whitespace']}")
    print(f"   Other: {removed_categories['other']}")
    print("")
    print(f"📊 Total removed: {removed_count}")
    print(f"📊 Kept: {len(cleaned_items)} valid entries")
    if original_count > 0:
        print(f"📊 Reduction: {removed_count / original_count * 100:.1f}%")

if __name__ == "__main__":
    clean_data()













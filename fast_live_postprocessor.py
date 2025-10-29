#!/usr/bin/env python3
"""
Fast Live Postprocessor for ATC Voice System
Processes individual chunks quickly for real-time updates.
"""

import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import subprocess

# Configuration
TRANSCRIPTS_FILE = Path("src/data/logs/transcripts/transcripts.json")
CATEGORIZED_FILE = Path("src/data/logs/transcripts/categorized_transcription_results.json")
POSTPROCESS_SCRIPT = Path("src/nlp_analysis/postprocess.py")
LOG_FILE = Path("logs/fast_live_postprocessor.log")

def log_message(message):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    # Also write to log file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def get_last_processed_chunks():
    """Get the chunk numbers that have already been processed."""
    if not CATEGORIZED_FILE.exists():
        return set()
    
    try:
        with open(CATEGORIZED_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        processed_chunks = set()
        for item in data.get('items', []):
            chunk_num = item.get('chunk_number')
            if chunk_num is not None:
                processed_chunks.add(chunk_num)
        
        return processed_chunks
    except Exception as e:
        log_message(f"❌ Error reading categorized file: {e}")
        return set()

def get_new_chunks():
    """Get chunk numbers that are new (not yet processed)."""
    if not TRANSCRIPTS_FILE.exists():
        return []
    
    try:
        with open(TRANSCRIPTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        processed_chunks = get_last_processed_chunks()
        all_items = data.get('items', [])
        
        new_chunks = []
        for item in all_items:
            chunk_num = item.get('chunk_number')
            if chunk_num is not None and chunk_num not in processed_chunks:
                new_chunks.append(chunk_num)
        
        return sorted(new_chunks)
    except Exception as e:
        log_message(f"❌ Error reading transcripts file: {e}")
        return []

def process_single_chunk(chunk_number):
    """Process a single chunk quickly."""
    try:
        log_message(f"🔄 Processing chunk {chunk_number}...")
        
        # Load current data
        with open(TRANSCRIPTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find the specific chunk
        target_item = None
        for item in data.get('items', []):
            if item.get('chunk_number') == chunk_number:
                target_item = item
                break
        
        if not target_item:
            log_message(f"❌ Chunk {chunk_number} not found")
            return False
        
        # Load existing categorized data
        if CATEGORIZED_FILE.exists():
            with open(CATEGORIZED_FILE, 'r', encoding='utf-8') as f:
                categorized_data = json.load(f)
        else:
            categorized_data = {"items": [], "metadata": {"total_items": 0}}
        
        # Simple categorization (basic implementation)
        raw_text = target_item.get("raw_transcription", "").lower()
        
        # Basic category detection
        category = "Miscellaneous"
        if any(word in raw_text for word in ["climb", "descend", "altitude", "level"]):
            category = "Altitude Clearances"
        elif any(word in raw_text for word in ["turn", "heading", "direct"]):
            category = "Heading Vectors"
        elif any(word in raw_text for word in ["contact", "switch", "frequency"]):
            category = "Frequency Handoffs"
        elif any(word in raw_text for word in ["mayday", "emergency", "pan-pan"]):
            category = "Emergency Declarations"
        
        # Basic airline detection
        airline = "Unknown"
        if "delta" in raw_text:
            airline = "Delta Air Lines"
        elif "american" in raw_text:
            airline = "American Airlines"
        elif "united" in raw_text:
            airline = "United Airlines"
        elif "jetblue" in raw_text:
            airline = "JetBlue Airways"
        
        # Add categorization to item
        target_item["category"] = category
        target_item["airline"] = airline
        target_item["duplicate_flag"] = False
        
        # Append to categorized data
        categorized_data["items"].append(target_item)
        categorized_data["metadata"]["total_items"] = len(categorized_data["items"])
        
        # Save updated data
        with open(CATEGORIZED_FILE, 'w', encoding='utf-8') as f:
            json.dump(categorized_data, f, indent=2, ensure_ascii=False)
        
        log_message(f"✅ Chunk {chunk_number} processed successfully")
        return True
        
    except Exception as e:
        log_message(f"❌ Error processing chunk {chunk_number}: {e}")
        return False

def main():
    """Main fast live monitoring loop."""
    log_message("🚀 Starting Fast Live Postprocessor")
    log_message(f"📁 Monitoring: {TRANSCRIPTS_FILE}")
    log_message(f"📊 Output: {CATEGORIZED_FILE}")
    log_message(f"📝 Log: {LOG_FILE}")
    log_message("Press Ctrl+C to stop")
    log_message("-" * 60)
    
    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    last_check_time = time.time()
    check_interval = 1  # Check every 1 second for maximum responsiveness
    
    try:
        while True:
            current_time = time.time()
            
            # Check for new chunks every second
            if current_time - last_check_time >= check_interval:
                new_chunks = get_new_chunks()
                
                if new_chunks:
                    log_message(f"🆕 Found {len(new_chunks)} new chunks: {new_chunks}")
                    
                    # Process chunks individually for speed
                    processed_count = 0
                    for chunk_num in new_chunks:
                        if process_single_chunk(chunk_num):
                            processed_count += 1
                    
                    log_message(f"✅ Successfully processed {processed_count}/{len(new_chunks)} chunks")
                
                last_check_time = current_time
            
            time.sleep(0.5)  # Check every 500ms
            
    except KeyboardInterrupt:
        log_message("\n🛑 Stopping Fast Live Postprocessor...")
        log_message("✅ Fast Live Postprocessor stopped")
    except Exception as e:
        log_message(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

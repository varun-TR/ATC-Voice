#!/usr/bin/env python3
"""
Live Postprocessor for ATC Voice System
Continuously monitors transcripts.json for new chunks and processes them automatically.
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
POSTPROCESS_SCRIPT = Path("src/nlp_analysis/atlas.py")
LOG_FILE = Path("logs/live_postprocessor.log")

def log_message(message):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    # Also write to log file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def get_file_size(file_path):
    """Get file size, return 0 if file doesn't exist."""
    try:
        return file_path.stat().st_size
    except FileNotFoundError:
        return 0

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

def run_postprocessing():
    """Run the postprocessing script with timeout."""
    try:
        log_message("🔄 Running postprocessing...")
        result = subprocess.run([
            sys.executable, str(POSTPROCESS_SCRIPT)
        ], capture_output=True, text=True, cwd=Path.cwd(), timeout=60)  # 60 second timeout
        
        if result.returncode == 0:
            log_message("✅ Postprocessing completed successfully")
            return True
        else:
            log_message(f"❌ Postprocessing failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log_message("⏰ Postprocessing timed out after 60 seconds")
        return False
    except Exception as e:
        log_message(f"❌ Error running postprocessing: {e}")
        return False

def main():
    """Main live monitoring loop."""
    log_message("🚀 Starting Live Postprocessor")
    log_message(f"📁 Monitoring: {TRANSCRIPTS_FILE}")
    log_message(f"📊 Output: {CATEGORIZED_FILE}")
    log_message(f"📝 Log: {LOG_FILE}")
    log_message("Press Ctrl+C to stop")
    log_message("-" * 60)
    
    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    last_file_size = get_file_size(TRANSCRIPTS_FILE)
    last_check_time = time.time()
    check_interval = 2  # Check every 2 seconds for faster response
    
    try:
        while True:
            current_time = time.time()
            
            # Check if file has changed
            current_file_size = get_file_size(TRANSCRIPTS_FILE)
            
            if current_file_size > last_file_size:
                log_message(f"📈 File size changed: {last_file_size} → {current_file_size}")
                
                # Check for new chunks
                new_chunks = get_new_chunks()
                
                if new_chunks:
                    log_message(f"🆕 Found {len(new_chunks)} new chunks: {new_chunks}")
                    
                    # Run postprocessing
                    if run_postprocessing():
                        log_message(f"✅ Successfully processed {len(new_chunks)} new chunks")
                    else:
                        log_message("❌ Failed to process new chunks")
                else:
                    log_message("ℹ️ No new chunks to process")
                
                last_file_size = current_file_size
            
            # Periodic check even if file size hasn't changed (backup)
            elif current_time - last_check_time >= check_interval:
                new_chunks = get_new_chunks()
                if new_chunks:
                    log_message(f"🔄 Periodic check found {len(new_chunks)} new chunks: {new_chunks}")
                    if run_postprocessing():
                        log_message(f"✅ Successfully processed {len(new_chunks)} new chunks")
                last_check_time = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        log_message("\n🛑 Stopping Live Postprocessor...")
        log_message("✅ Live Postprocessor stopped")
    except Exception as e:
        log_message(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Utility script to repair corrupted JSON files.
Extracts valid JSON data from files with extra data after closing brace.
"""

import json
import sys
from pathlib import Path
import shutil
from datetime import datetime

def repair_json_file(file_path):
    """Repair a corrupted JSON file by extracting valid data."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"🔍 Analyzing: {file_path}")
    
    # Create backup
    backup_path = file_path.with_suffix(f'.json.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copy2(file_path, backup_path)
    print(f"💾 Backup created: {backup_path}")
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try to parse
    try:
        data = json.loads(content)
        print("✅ JSON is valid - no repair needed")
        return True
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON Error detected: {e}")
        
        if "Extra data" not in str(e):
            print(f"❌ Cannot repair this type of error: {e}")
            return False
        
        # Extract valid JSON
        print(f"🔧 Attempting to repair...")
        
        try:
            # Find the last valid closing brace before error position
            valid_content = content[:e.pos].rstrip()
            
            # Find the last complete JSON object
            brace_count = 0
            last_valid_pos = 0
            for i, char in enumerate(valid_content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_pos = i + 1
            
            if last_valid_pos == 0:
                print("❌ Could not find valid JSON structure")
                return False
            
            # Extract valid JSON
            valid_json = content[:last_valid_pos]
            data = json.loads(valid_json)
            
            print(f"✅ Successfully extracted valid JSON")
            print(f"   Items recovered: {data.get('metadata', {}).get('total_items', 0)}")
            
            # Extract corrupted part for analysis
            corrupted_part = content[last_valid_pos:e.pos + 200]
            print(f"\n📋 Corrupted data that was removed:")
            print(f"   {repr(corrupted_part[:200])}")
            
            # Write repaired file atomically
            temp_path = file_path.with_suffix('.json.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_path.replace(file_path)
            
            print(f"\n✅ File repaired successfully!")
            print(f"   Original file: {backup_path}")
            print(f"   Repaired file: {file_path}")
            
            return True
            
        except Exception as repair_error:
            print(f"❌ Repair failed: {repair_error}")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python repair_json.py <json_file_path>")
        print("\nExample:")
        print("  python repair_json.py src/data/logs/transcripts/categorized_transcription_results.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = repair_json_file(file_path)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()


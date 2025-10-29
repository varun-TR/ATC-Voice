#!/usr/bin/env python3
"""
ATC Voice Postprocessing Pipeline
This script demonstrates the complete pipeline:
1. Process transcripts.json with postprocessing
2. Append new chunks to categorized_transcription_results.json
3. Start the dashboard to visualize results
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def run_postprocessing():
    """Run the postprocessing script on transcripts.json"""
    print("🔄 Running postprocessing on transcripts.json...")
    
    try:
        # Run the postprocessing script
        result = subprocess.run([
            sys.executable, 
            "src/nlp_analysis/postprocess.py"
        ], cwd="/home/atc_voice/ATC-Voice", capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Postprocessing completed successfully!")
            print("Output:", result.stdout)
        else:
            print("❌ Postprocessing failed!")
            print("Error:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running postprocessing: {e}")
        return False
    
    return True

def start_dashboard():
    """Start the Streamlit dashboard"""
    print("🚀 Starting dashboard...")
    
    try:
        # Start dashboard in background
        dashboard_process = subprocess.Popen([
            "/home/stanjore/.local/bin/streamlit", 
            "run", 
            "src/dashboard/app.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ], cwd="/home/atc_voice/ATC-Voice")
        
        print("✅ Dashboard started!")
        print("🌐 Dashboard URL: http://localhost:8501")
        print("📊 Dashboard will show categorized results from categorized_transcription_results.json")
        
        return dashboard_process
        
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        return None

def check_files():
    """Check if required files exist"""
    base_dir = Path("/home/atc_voice/ATC-Voice")
    
    files_to_check = [
        "src/data/logs/transcripts/transcripts.json",
        "src/data/logs/transcripts/categorized_transcription_results.json",
        "config/category_dict.json",
        "config/airline_callsign.json",
        "src/nlp_analysis/postprocess.py",
        "src/dashboard/app.py"
    ]
    
    print("📁 Checking required files...")
    
    missing_files = []
    for file_path in files_to_check:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing files: {missing_files}")
        return False
    
    print("✅ All required files present!")
    return True

def show_file_stats():
    """Show statistics about the data files"""
    print("\n📊 Data File Statistics:")
    
    transcripts_file = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/transcripts.json")
    categorized_file = Path("/home/atc_voice/ATC-Voice/src/data/logs/transcripts/categorized_transcription_results.json")
    
    if transcripts_file.exists():
        size_mb = transcripts_file.stat().st_size / (1024 * 1024)
        print(f"📝 transcripts.json: {size_mb:.2f} MB")
    
    if categorized_file.exists():
        size_mb = categorized_file.stat().st_size / (1024 * 1024)
        print(f"📊 categorized_transcription_results.json: {size_mb:.2f} MB")

def main():
    print("=" * 70)
    print("🛫 ATC VOICE POSTPROCESSING PIPELINE")
    print("=" * 70)
    
    # Check files
    if not check_files():
        print("❌ Missing required files. Please ensure all files exist.")
        sys.exit(1)
    
    # Show file stats
    show_file_stats()
    
    # Run postprocessing
    if not run_postprocessing():
        print("❌ Postprocessing failed. Exiting.")
        sys.exit(1)
    
    # Start dashboard
    dashboard_process = start_dashboard()
    if not dashboard_process:
        print("❌ Failed to start dashboard. Exiting.")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 70)
    print("📋 What happened:")
    print("1. ✅ Processed transcripts.json with categorization")
    print("2. ✅ Appended new chunks to categorized_transcription_results.json")
    print("3. ✅ Started dashboard to visualize results")
    print("\n🌐 Dashboard is running at: http://localhost:8501")
    print("📊 The dashboard reads from categorized_transcription_results.json")
    print("\n🔄 For future updates:")
    print("   - When transcripts.json gets new chunks, run postprocessing again")
    print("   - The script will automatically append only new chunks")
    print("   - Dashboard will show updated results")
    
    try:
        # Keep the script running to maintain dashboard
        print("\n⏳ Dashboard is running... Press Ctrl+C to stop")
        dashboard_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping dashboard...")
        dashboard_process.terminate()
        print("✅ Dashboard stopped.")

if __name__ == "__main__":
    main()



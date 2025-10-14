#!/bin/bash

# ATC Voice Live Postprocessing Script

echo "🏷️ Starting ATC Live Postprocessing..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
echo "Checking dependencies..."
python3 -c "import watchdog, json, re, sys, time, os" 2>/dev/null || {
    echo "Installing postprocessing dependencies..."
    pip install watchdog
}

# Start live postprocessing
echo "Starting Live Postprocessing..."
echo "This will monitor: src/data/logs/transcripts/transcription_results.json"
echo "And output to: src/data/logs/transcripts/categorized_transcription_results.json"
echo ""
echo "The script will automatically process new transcripts as they appear"
echo "Press Ctrl+C to stop monitoring"
echo ""

python src/nlp_analysis/postprocess.py --live

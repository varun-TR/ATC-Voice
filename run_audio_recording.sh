#!/bin/bash

# ATC Voice Audio Recording & Transcription Startup Script

echo "🎙️ Starting ATC Voice Audio Recording & Transcription System..."

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
python3 -c "import librosa, faster_whisper, pydub, numpy" 2>/dev/null || {
    echo "Installing audio processing dependencies..."
    pip install librosa faster-whisper pydub numpy
}

# Create logs directory if it doesn't exist
mkdir -p logs

echo ""
echo "🎙️ Starting Audio Recording & Transcription:"
echo "  - Stream: LiveATC NY Center Sector 9"
echo "  - Output: src/data/raw/ (audio files)"
echo "  - Transcription: src/data/logs/transcripts/transcription_results.json"
echo "  - Communications: src/data/logs/atc_communications.txt"
echo ""
echo "Press Ctrl+C to stop recording"
echo ""

# Start audio recording and transcription system
python src/utils/all_in_one.py





#!/bin/bash

# ATC Voice Complete Live System Startup Script

echo "🛫 Starting ATC Voice Complete Live System..."
echo "=============================================="

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
python3 -c "import streamlit, pandas, numpy, plotly, watchdog, librosa, faster_whisper, pydub" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install streamlit pandas numpy plotly watchdog librosa faster-whisper pydub
}

# Create logs directory if it doesn't exist
mkdir -p logs

echo ""
echo "🚀 Starting Complete Live System:"
echo "1. Audio Recording & Transcription (all_in_one.py)"
echo "2. Live Postprocessing (monitors transcription_results.json)"
echo "3. Live Dashboard (monitors both communications and categorized transcriptions)"
echo ""

# Start audio recording and transcription system in background
echo "Starting audio recording and transcription system..."
nohup python src/utils/all_in_one.py > logs/audio_recording.log 2>&1 &
AUDIO_PID=$!

# Wait a moment for audio system to initialize
sleep 5

# Start live postprocessing in background
echo "Starting live postprocessing..."
nohup python src/nlp_analysis/postprocess.py --live > logs/postprocessing.log 2>&1 &
POSTPROCESSING_PID=$!

# Wait a moment for postprocessing to initialize
sleep 2

# Start dashboard
echo "Starting live dashboard..."
echo "Dashboard will be available at: http://localhost:8501"
echo ""
echo "Complete live system active:"
echo "  - Audio Recording: LiveATC stream → src/data/raw/"
echo "  - Transcription: Audio files → src/data/logs/transcripts/transcription_results.json"
echo "  - Communications: LiveATC stream → src/data/logs/atc_communications.txt"
echo "  - Categorization: Raw transcripts → src/data/logs/transcripts/categorized_transcription_results.json"
echo "  - Dashboard: Real-time monitoring of all components"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    kill $AUDIO_PID 2>/dev/null
    kill $POSTPROCESSING_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Start dashboard (this will block)
streamlit run src/dashboard/app.py --server.headless true

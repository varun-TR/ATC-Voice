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
python3 -c "import streamlit, pandas, numpy, plotly, watchdog" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install streamlit pandas numpy plotly watchdog
}

echo ""
echo "🚀 Starting Live Components:"
echo "1. Live Postprocessing (monitors transcription_results.json)"
echo "2. Live Dashboard (monitors both communications and categorized transcriptions)"
echo ""

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
echo "Live monitoring active for:"
echo "  - Communications: src/data/logs/atc_communications.txt"
echo "  - Transcriptions: src/data/logs/transcripts/transcription_results.json"
echo "  - Categorized: src/data/logs/transcripts/categorized_transcription_results.json"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $POSTPROCESSING_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Start dashboard (this will block)
streamlit run src/dashboard/app.py --server.headless true

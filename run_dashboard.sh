#!/bin/bash

# ATC Voice Dashboard Startup Script

echo "🛫 Starting ATC Voice Communications Dashboard..."

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
python3 -c "import streamlit, pandas, numpy, plotly" 2>/dev/null || {
    echo "Installing dashboard dependencies..."
    pip install streamlit pandas numpy plotly
}

# Start the dashboard
echo "Starting Live ATC Dashboard..."
echo "Dashboard will be available at: http://localhost:8501"
echo "This dashboard reads live data from:"
echo "  - Transcriptions: src/data/logs/transcripts/categorized_transcription_results.json"
echo "  - Communications: src/data/logs/atc_communications.txt"
echo ""
echo "The dashboard updates automatically every 5 seconds"
echo "Press Ctrl+C to stop the dashboard"
echo ""

streamlit run src/dashboard/app.py --server.headless true

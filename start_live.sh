#!/bin/bash

# Quick Start Script for ATC Voice Live System
# Starts the unified all-in-one system with proper Ctrl+C handling

echo "🚀 Starting ATC Voice Live System (Unified All-in-One)"
echo "======================================================"

# Check if we're in the right directory
if [ ! -f "src/nlp_analysis/postprocess.py" ]; then
    echo "❌ Error: Please run this script from the ATC-Voice root directory"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Please run ./run_live_system.sh first"
    exit 1
fi

# Clean up any existing processes (except logext.py - don't touch it!)
echo "🧹 Cleaning up existing processes..."
echo "ℹ️ Preserving logext.py (communications detection) - already running"
pkill -f "python.*fast_live_postprocessor.py" 2>/dev/null || true
pkill -f "streamlit.*app.py" 2>/dev/null || true
pkill -f "python.*all_in_one.py" 2>/dev/null || true
lsof -ti :8501 | xargs kill -9 2>/dev/null || true
sleep 2

# Check if logext.py is running (don't start it, just check)
if ps aux | grep -q "python.*logext.py" | grep -v grep; then
    LOGEXT_PID=$(ps aux | grep "python.*logext.py" | grep -v grep | awk '{print $2}' | head -1)
    echo "✅ Communications detection already running (PID: $LOGEXT_PID) - preserved"
else
    echo "⚠️ Communications detection not running - but not starting it per request"
    LOGEXT_PID="N/A"
fi

# Function to handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down ATC Voice Live System..."
    echo "=========================================="
    
    # Kill all-in-one process
    pkill -f "python.*all_in_one.py" 2>/dev/null || true
    
    # Kill any remaining postprocessor processes
    pkill -f "python.*fast_live_postprocessor.py" 2>/dev/null || true
    
    # Kill dashboard
    pkill -f "streamlit.*app.py" 2>/dev/null || true
    lsof -ti :8501 | xargs kill -9 2>/dev/null || true
    
    echo "✅ All processes stopped"
    echo "ℹ️ Note: logext.py (communications detection) continues running"
    echo ""
    echo "📋 Log Files:"
    echo "  - Communications: logs/logext.log"
    echo "  - All-in-One: logs/all_in_one.log"
    echo "  - Postprocessor: logs/fast_live_postprocessor.log"
    echo "  - Dashboard: logs/dashboard.log"
    echo ""
    echo "👋 Goodbye!"
    exit 0
}

# Set up signal handlers for Ctrl+C
trap cleanup SIGINT SIGTERM

# Start the unified all-in-one system
echo "🎙️ Starting unified ATC recording & transcription system..."
echo "📁 This includes:"
echo "   - Live audio recording from ATC stream"
echo "   - Real-time transcription with ATC-specialized Whisper"
echo "   - Live postprocessing and categorization"
echo "   - Dashboard at http://localhost:8501"
echo ""
echo "⌨️  Press Ctrl+C to stop the system"
echo "======================================================"

# Run the all-in-one system in foreground so Ctrl+C works properly
python3 src/utils/all_in_one.py

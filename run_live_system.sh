#!/bin/bash

# ATC Voice Complete Live System Startup Script
# Features: Audio Recording → ATC Transcription → Automatic Processing → Live Dashboard
# Uses jlvdoorn/whisper-large-v3-atco2-asr model for superior aviation transcription

echo "🛫 Starting ATC Voice Complete Live System..."
echo "============================================="

# Check if we're in the right directory
if [ ! -f "src/nlp_analysis/postprocess.py" ]; then
    echo "❌ Error: Please run this script from the ATC-Voice root directory"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install system dependencies if needed
echo "🔍 Checking system dependencies..."
python3 -c "import watchdog, streamlit, pandas, plotly, psutil" 2>/dev/null || {
    echo "📦 Installing Python dependencies..."
    pip install watchdog streamlit pandas plotly psutil
}

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p src/data/logs/transcripts
mkdir -p src/data/raw

echo ""
echo "🚀 Starting Complete Live System:"
echo "1. Audio Recording & ATC Transcription (all_in_one.py)"
echo "2. Automatic Processing (monitors transcripts.json for new chunks)"
echo "3. Live Dashboard (real-time ATC communications and categorized transcriptions)"
echo ""

# Check if required files exist
echo "🔍 Checking required files..."
REQUIRED_FILES=(
    "src/utils/all_in_one.py"
    "src/nlp_analysis/postprocess.py"
    "src/dashboard/app.py"
    "config/category_dict.json"
    "config/airline_callsign.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "✅ All required files present"

# Check if transcripts.json exists, create if not
if [ ! -f "src/data/logs/transcripts/transcripts.json" ]; then
    echo "📝 Creating initial transcripts.json..."
    echo '{"created_utc": "", "model_used": "jlvdoorn/whisper-large-v3-atco2-asr", "items": [], "last_updated_utc": ""}' > src/data/logs/transcripts/transcripts.json
fi

# Function to clean up any existing processes
cleanup_existing_processes() {
    echo "🧹 Cleaning up any existing processes..."
    
    # Kill any existing all_in_one.py processes
    pkill -f "python.*all_in_one.py" 2>/dev/null || true
    
    # Kill any existing postprocess.py processes
    pkill -f "python.*postprocess.py" 2>/dev/null || true
    
    # Kill any existing live_postprocessor.py processes
    pkill -f "python.*live_postprocessor.py" 2>/dev/null || true
    
    # Kill any existing fast_live_postprocessor.py processes
    pkill -f "python.*fast_live_postprocessor.py" 2>/dev/null || true
    
    # Kill any existing streamlit processes
    pkill -f "streamlit.*app.py" 2>/dev/null || true
    
    # Kill any processes using port 8501 or 8502
    lsof -ti :8501 | xargs kill -9 2>/dev/null || true
    lsof -ti :8502 | xargs kill -9 2>/dev/null || true
    
    sleep 2
    echo "✅ Cleanup complete"
}

# Initialize PIDs
AUDIO_PID=""
PROCESSING_PID=""
DASHBOARD_PID=""

# Clean up any existing processes
cleanup_existing_processes

# Start audio recording and transcription system in background
echo "🎙️ Starting audio recording and transcription system..."
if [ -f "src/utils/all_in_one.py" ]; then
    nohup python3 src/utils/all_in_one.py > logs/audio_recording.log 2>&1 &
    AUDIO_PID=$!
    echo "✅ Audio system started (PID: $AUDIO_PID)"
else
    echo "⚠️ Audio system not available (all_in_one.py not found)"
fi

# Wait a moment for audio system to initialize
if [ ! -z "$AUDIO_PID" ]; then
    echo "⏳ Waiting for audio system to initialize..."
    sleep 5
fi

# Start automatic processing service in background
echo "🔄 Starting automatic processing service..."
nohup python3 fast_live_postprocessor.py > logs/auto_processing.log 2>&1 &
PROCESSING_PID=$!
echo "✅ Automatic processing started (PID: $PROCESSING_PID)"

# Wait a moment for processing to initialize
echo "⏳ Waiting for processing service to initialize..."
sleep 3

# Check if port 8501 is in use and kill any existing processes
echo "🔍 Checking port 8501..."
if lsof -i :8501 >/dev/null 2>&1; then
    echo "⚠️ Port 8501 is in use. Killing existing processes..."
    lsof -ti :8501 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Start dashboard in background
echo "🌐 Starting live dashboard..."
nohup streamlit run src/dashboard/app.py --server.headless true --server.port 8501 > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
echo "Dashboard will be available at: http://localhost:8501"
echo ""

# Wait a moment for dashboard to initialize and verify it's running
echo "⏳ Waiting for dashboard to initialize..."
sleep 5

# Verify dashboard is actually running
if ! kill -0 $DASHBOARD_PID 2>/dev/null; then
    echo "❌ Dashboard failed to start. Checking logs..."
    echo "Last 10 lines of dashboard log:"
    tail -10 logs/dashboard.log
    echo ""
    echo "Trying to start dashboard on alternative port..."
    nohup streamlit run src/dashboard/app.py --server.headless true --server.port 8502 > logs/dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo "✅ Dashboard started on port 8502 (PID: $DASHBOARD_PID)"
    echo "Dashboard will be available at: http://localhost:8502"
fi

# Display system status
echo "🎉 Complete Live System Active:"
echo "================================"
if [ ! -z "$AUDIO_PID" ]; then
    echo "🎙️ Audio Recording: LiveATC stream → src/data/raw/ (PID: $AUDIO_PID)"
    echo "📝 ATC Transcription: Audio files → transcripts.json (ATC-specialized model)"
fi
echo "🔄 Automatic Processing: transcripts.json → categorized_transcription_results.json (PID: $PROCESSING_PID)"
if [ ! -z "$DASHBOARD_PID" ]; then
    if kill -0 $DASHBOARD_PID 2>/dev/null; then
        # Check which port the dashboard is actually using
        DASHBOARD_PORT=$(lsof -p $DASHBOARD_PID | grep LISTEN | awk '{print $9}' | cut -d: -f2 | head -1)
        if [ -z "$DASHBOARD_PORT" ]; then
            DASHBOARD_PORT="8501"
        fi
        echo "🌐 Live Dashboard: Real-time monitoring at http://localhost:$DASHBOARD_PORT (PID: $DASHBOARD_PID)"
    else
        echo "❌ Live Dashboard: Failed to start"
    fi
else
    echo "❌ Live Dashboard: Not started"
fi
echo "📊 Communications: LiveATC stream → atc_communications.txt"
echo ""
echo "📋 Log Files:"
echo "  - Audio Recording: logs/audio_recording.log"
echo "  - Auto Processing: logs/auto_processing.log"
echo "  - Dashboard: logs/dashboard.log"
echo ""
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    
    if [ ! -z "$AUDIO_PID" ]; then
        echo "  Stopping audio system (PID: $AUDIO_PID)..."
        kill $AUDIO_PID 2>/dev/null
    fi
    
    if [ ! -z "$PROCESSING_PID" ]; then
        echo "  Stopping processing service (PID: $PROCESSING_PID)..."
        kill $PROCESSING_PID 2>/dev/null
    fi
    
    if [ ! -z "$DASHBOARD_PID" ]; then
        echo "  Stopping dashboard (PID: $DASHBOARD_PID)..."
        kill $DASHBOARD_PID 2>/dev/null
    fi
    
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Keep the script running and monitor services
echo "🔄 System monitoring active. Press Ctrl+C to stop all services."
echo ""

# Monitor loop
while true; do
    # Check if any service has died
    if [ ! -z "$AUDIO_PID" ] && ! kill -0 $AUDIO_PID 2>/dev/null; then
        echo "⚠️ Audio service (PID: $AUDIO_PID) has stopped unexpectedly"
    fi
    
    if [ ! -z "$PROCESSING_PID" ] && ! kill -0 $PROCESSING_PID 2>/dev/null; then
        echo "⚠️ Processing service (PID: $PROCESSING_PID) has stopped unexpectedly"
    fi
    
    if [ ! -z "$DASHBOARD_PID" ] && ! kill -0 $DASHBOARD_PID 2>/dev/null; then
        echo "⚠️ Dashboard service (PID: $DASHBOARD_PID) has stopped unexpectedly"
    fi
    
    sleep 10
done

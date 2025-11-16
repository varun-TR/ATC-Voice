#!/bin/bash

# ATC Voice Complete Live System Startup Script
# Features: Audio Recording → ATC Transcription → Automatic Processing → Live Dashboard
# Uses jlvdoorn/whisper-large-v3-atco2-asr model for superior aviation transcription

echo "🛫 Starting ATC Voice Complete Live System..."
echo "============================================="

# Check if we're in the right directory
if [ ! -f "src/nlp_analysis/atlas.py" ]; then
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
echo "2. Atlas.py - Cleans & Categorizes (monitors transcripts.json, writes to cleaned_transcripts.json)"
echo "3. Live Dashboard (real-time ATC communications from cleaned_transcripts.json)"
echo ""

# Check if required files exist
echo "🔍 Checking required files..."
REQUIRED_FILES=(
    "src/utils/all_in_one.py"
    "src/nlp_analysis/atlas.py"
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
    
    # Kill any existing atlas.py processes
    pkill -f "python.*atlas.py" 2>/dev/null || true
    
    # Kill any existing live_postprocessor.py processes
    pkill -f "python.*live_postprocessor.py" 2>/dev/null || true
    
    
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
CLEANER_PID=""
DASHBOARD_PID=""
MEMORY_MONITOR_PID=""

# Check available memory before starting
echo "🔍 Checking system memory..."
available_mem=$(free -m | awk 'NR==2{print $7}')
swap_percent=$(free | awk 'NR==3{if ($2>0) print int($3/$2*100); else print 0}')
echo "   Available memory: ${available_mem}MB"
echo "   Swap usage: ${swap_percent}%"

if [ "$available_mem" -lt 1024 ]; then
    echo "⚠️  WARNING: Available memory is low (< 1GB)"
    echo "   System may experience OOM issues"
    echo "   Consider:"
    echo "   - Closing other applications"
    echo "   - Adding more swap space"
    echo "   - Upgrading system RAM"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

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

# Start atlas.py service in background (cleans and categorizes transcripts)
echo "🧹 Starting atlas.py service (cleaner & categorizer)..."
nohup python3 src/nlp_analysis/atlas.py > logs/atlas.log 2>&1 &
CLEANER_PID=$!
echo "✅ Atlas.py started (PID: $CLEANER_PID)"

# Wait a moment for cleaner to initialize
sleep 2

# Memory monitor disabled (user preference)
MEMORY_MONITOR_PID=""
# # Uncomment to enable memory monitor
# echo "🔍 Starting memory monitor..."
# if [ -f "monitor_memory.py" ]; then
#     nohup python3 monitor_memory.py > logs/memory_monitor.log 2>&1 &
#     MEMORY_MONITOR_PID=$!
#     echo "✅ Memory monitor started (PID: $MEMORY_MONITOR_PID)"
# else
#     echo "⚠️ Memory monitor script not found (monitor_memory.py)"
# fi

# Get the server's IP address
SERVER_IP=$(hostname -I | awk '{print $1}')

# Check if port 8501 is in use and kill any existing processes
echo "🔍 Checking port 8501..."
if lsof -i :8501 >/dev/null 2>&1; then
    echo "⚠️ Port 8501 is in use. Killing existing processes..."
    lsof -ti :8501 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Start dashboard in background with external access enabled
echo "🌐 Starting live dashboard..."
nohup streamlit run src/dashboard/app.py \
    --server.headless true \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.enableCORS false \
    --server.enableXsrfProtection false > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
echo "📱 Dashboard accessible at:"
echo "   - Local: http://localhost:8501"
echo "   - Network: http://${SERVER_IP}:8501"
echo ""

# Wait a moment for dashboard to initialize
echo "⏳ Waiting for dashboard to initialize..."
sleep 5

# Verify dashboard is actually running
if ! kill -0 $DASHBOARD_PID 2>/dev/null; then
    echo "❌ Dashboard failed to start. Checking logs..."
    echo "Last 10 lines of dashboard log:"
    tail -10 logs/dashboard.log
    echo ""
    echo "Trying to start dashboard on alternative port..."
    nohup streamlit run src/dashboard/app.py \
        --server.headless true \
        --server.port 8502 \
        --server.address 0.0.0.0 \
        --server.enableCORS false \
        --server.enableXsrfProtection false > logs/dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo "✅ Dashboard started on port 8502 (PID: $DASHBOARD_PID)"
    echo "📱 Dashboard accessible at:"
    echo "   - Local: http://localhost:8502"
    echo "   - Network: http://${SERVER_IP}:8502"
fi

# Display system status
echo "🎉 Complete Live System Active:"
echo "================================"
if [ ! -z "$AUDIO_PID" ]; then
    echo "🎙️ Audio Recording: LiveATC stream → src/data/raw/ (PID: $AUDIO_PID)"
    echo "📝 ATC Transcription: Audio files → transcripts.json (ATC-specialized model)"
fi
if [ ! -z "$CLEANER_PID" ]; then
    echo "🧹 Atlas.py: Cleans and categorizes transcripts.json → cleaned_transcripts.json (PID: $CLEANER_PID)"
fi
if [ ! -z "$DASHBOARD_PID" ] && kill -0 $DASHBOARD_PID 2>/dev/null; then
    # Check which port the dashboard is actually using
    DASHBOARD_PORT=$(lsof -p $DASHBOARD_PID | grep LISTEN | awk '{print $9}' | cut -d: -f2 | head -1)
    if [ -z "$DASHBOARD_PORT" ]; then
        DASHBOARD_PORT="8501"
    fi
    echo "🌐 Live Dashboard: Real-time monitoring (PID: $DASHBOARD_PID)"
    echo "   - Local: http://localhost:$DASHBOARD_PORT"
    echo "   - Network: http://${SERVER_IP}:$DASHBOARD_PORT"
else
    echo "📊 Live Dashboard: Manual control enabled"
    echo "   - Start with: ./start_dashboard.sh"
    echo "   - Will NOT auto-restart if stopped"
fi
echo "📊 Communications: LiveATC stream → atc_communications.txt"
echo ""
echo "📋 Log Files:"
echo "  - Audio Recording: logs/audio_recording.log"
echo "  - Atlas.py: logs/atlas.log"
echo "  - Dashboard: logs/dashboard.log (if started)"
echo ""
echo "🛑 Press Ctrl+C to stop all services"
echo "ℹ️  Auto-restart is DISABLED - services will NOT restart if they crash"
echo "   Dashboard WILL auto-start with the system"
echo "   To restart: Stop with Ctrl+C and run ./run_live_system.sh again"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    
    if [ ! -z "$AUDIO_PID" ]; then
        echo "  Stopping audio system (PID: $AUDIO_PID)..."
        kill $AUDIO_PID 2>/dev/null
    fi
    
    if [ ! -z "$CLEANER_PID" ]; then
        echo "  Stopping atlas.py (PID: $CLEANER_PID)..."
        kill $CLEANER_PID 2>/dev/null
    fi
    
    if [ ! -z "$DASHBOARD_PID" ]; then
        echo "  Stopping dashboard (PID: $DASHBOARD_PID)..."
        kill $DASHBOARD_PID 2>/dev/null
    fi
    
    echo "✅ All services stopped"
    exit 0
}

# Function to check available memory
check_memory() {
    # Get available memory in MB
    available_mem=$(free -m | awk 'NR==2{print $7}')
    swap_percent=$(free | awk 'NR==3{if ($2>0) print int($3/$2*100); else print 0}')
    
    if [ "$available_mem" -lt 512 ] || [ "$swap_percent" -gt 80 ]; then
        echo "⚠️  WARNING: Low memory detected!"
        echo "   Available: ${available_mem}MB, Swap used: ${swap_percent}%"
        echo "   Running garbage collection..."
        python3 -c "import gc; gc.collect()"
        return 1
    fi
    return 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Keep the script running and monitor services
echo "🔄 System monitoring active. Press Ctrl+C to stop all services."
echo ""

# Monitor loop - NO AUTO-RESTART (reports only)
while true; do
    # Check if any service has died
    if [ ! -z "$AUDIO_PID" ] && ! kill -0 $AUDIO_PID 2>/dev/null; then
        echo "⚠️ Audio service (PID: $AUDIO_PID) has stopped unexpectedly"
        AUDIO_PID=""
    fi
    
    if [ ! -z "$CLEANER_PID" ] && ! kill -0 $CLEANER_PID 2>/dev/null; then
        echo "⚠️ Atlas.py (PID: $CLEANER_PID) has stopped unexpectedly"
        CLEANER_PID=""
    fi
    
    if [ ! -z "$DASHBOARD_PID" ] && ! kill -0 $DASHBOARD_PID 2>/dev/null; then
        echo "⚠️ Dashboard service (PID: $DASHBOARD_PID) has stopped unexpectedly"
        DASHBOARD_PID=""
    fi
    
    # Just monitor, no auto-restart
    sleep 10
done

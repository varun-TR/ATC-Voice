#!/bin/bash
# Stop all ATC Voice system processes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 Stopping ATC Voice System..."
echo "============================================="

# Read PID if exists
if [ -f .system_pid ]; then
    SYSTEM_PID=$(cat .system_pid)
    if ps -p $SYSTEM_PID > /dev/null 2>&1; then
        echo "Stopping main system process (PID: $SYSTEM_PID)..."
        kill $SYSTEM_PID 2>/dev/null
        sleep 2
        # Force kill if still running
        if ps -p $SYSTEM_PID > /dev/null 2>&1; then
            kill -9 $SYSTEM_PID 2>/dev/null
        fi
        rm -f .system_pid
    else
        echo "Main system process not found (may have already stopped)"
        rm -f .system_pid
    fi
fi

# Stop all individual processes
echo "Stopping individual services..."

# Stop audio recording
pkill -f "python.*all_in_one.py" 2>/dev/null && echo "  ✅ Stopped all_in_one.py" || echo "  ℹ️  all_in_one.py not running"

# Stop atlas.py
pkill -f "python.*atlas.py" 2>/dev/null && echo "  ✅ Stopped atlas.py" || echo "  ℹ️  atlas.py not running"

# Stop dashboard
pkill -f "streamlit.*app.py" 2>/dev/null && echo "  ✅ Stopped dashboard" || echo "  ℹ️  Dashboard not running"

# Stop any remaining run_live_system.sh processes
pkill -f "run_live_system.sh" 2>/dev/null && echo "  ✅ Stopped run_live_system.sh" || echo "  ℹ️  run_live_system.sh not running"

echo ""
echo "✅ System stopped!"
echo ""
echo "Note: logext.py is still running (separate process)"
echo "To stop it: pkill -f logext.py"








#!/bin/bash
# Start run_live_system.sh in a way that persists after VPN disconnect
# This script ensures the system continues running even if SSH/VPN connection drops

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛫 Starting ATC Voice System (Persistent Mode)..."
echo "============================================="
echo ""
echo "This will start the system and keep it running even after VPN disconnect."
echo "To stop, use: ./stop_system.sh"
echo ""

# Use nohup and redirect to null, then disown
# This ensures the script continues even if terminal closes
nohup bash run_live_system.sh > logs/system_startup.log 2>&1 &
SYSTEM_PID=$!

# Save PID to file for easy stopping
echo $SYSTEM_PID > .system_pid
echo "✅ System started in background (PID: $SYSTEM_PID)"
echo "📝 PID saved to .system_pid"
echo ""
echo "The system is now running in the background."
echo "You can safely disconnect from VPN - it will continue running."
echo ""
echo "To check status: ps aux | grep -E '(all_in_one|atlas|streamlit)' | grep -v grep"
echo "To stop: ./stop_system.sh"
echo ""
echo "Logs are being written to:"
echo "  - System startup: logs/system_startup.log"
echo "  - Audio: logs/audio_recording.log"
echo "  - Atlas: logs/atlas.log"
echo "  - Dashboard: logs/dashboard.log"








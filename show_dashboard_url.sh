#!/bin/bash

# Quick script to show dashboard URLs

echo "======================================================================"
echo "🌐 ATC VOICE DASHBOARD URLS"
echo "======================================================================"

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

# Check if dashboard is running
if pgrep -f "streamlit.*app.py" > /dev/null; then
    DASHBOARD_PORT=$(lsof -i -P -n | grep streamlit | grep LISTEN | awk '{print $9}' | cut -d: -f2 | head -1)
    
    if [ -z "$DASHBOARD_PORT" ]; then
        DASHBOARD_PORT="8501"
    fi
    
    echo "✅ Dashboard is RUNNING"
    echo ""
    echo "📱 Access from this computer:"
    echo "   http://localhost:$DASHBOARD_PORT"
    echo ""
    echo "🌍 Access from other devices on the network:"
    echo "   http://${SERVER_IP}:$DASHBOARD_PORT"
    echo ""
    echo "💡 Share this URL with others on your network!"
    echo ""
    echo "📝 Note: Make sure port $DASHBOARD_PORT is open in your firewall:"
    echo "   sudo ufw allow $DASHBOARD_PORT/tcp"
else
    echo "❌ Dashboard is NOT running"
    echo ""
    echo "To start the dashboard, run:"
    echo "   ./run_live_system.sh"
fi

echo "======================================================================"






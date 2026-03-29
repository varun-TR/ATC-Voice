#!/bin/bash

# Manual Dashboard Starter for ATC Voice System
# Run this script whenever you want to start the dashboard

echo "🌐 Starting ATC Voice Dashboard..."
echo "=================================="

# Check if dashboard is already running
if lsof -i :8501 >/dev/null 2>&1; then
    echo "⚠️  Dashboard already running on port 8501"
    echo "   Stop it first with: pkill -f 'streamlit.*app.py'"
    exit 1
fi

# Check if dashboard file exists
if [ ! -f "src/dashboard/app.py" ]; then
    echo "❌ Error: Dashboard file not found (src/dashboard/app.py)"
    exit 1
fi

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

# Start dashboard
echo "Starting dashboard on port 8501..."
nohup streamlit run src/dashboard/app.py \
    --server.headless true \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.enableCORS false \
    --server.enableXsrfProtection false > logs/dashboard.log 2>&1 &

DASHBOARD_PID=$!

# Wait for it to initialize
sleep 3

# Check if it started successfully
if kill -0 $DASHBOARD_PID 2>/dev/null; then
    echo "✅ Dashboard started successfully!"
    echo ""
    echo "📱 Access dashboard at:"
    echo "   - Local:   http://localhost:8501"
    echo "   - Network: http://${SERVER_IP}:8501"
    echo ""
    echo "Process ID: $DASHBOARD_PID"
    echo "Log file: logs/dashboard.log"
    echo ""
    echo "To stop: pkill -f 'streamlit.*app.py'"
else
    echo "❌ Failed to start dashboard"
    echo "Check logs: tail -f logs/dashboard.log"
    exit 1
fi


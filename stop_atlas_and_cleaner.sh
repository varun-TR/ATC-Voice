#!/bin/bash
# Stop atlas.py (replaces both old atlas.py and auto_cleaner.py)

echo "======================================================================"
echo "🛑 Stopping ATC Atlas and Auto-Cleaner"
echo "======================================================================"

# Atlas.py is already stopped above (it replaces both old scripts)

# Stop atlas.py
echo "🏷️  Stopping atlas.py..."
pkill -f "atlas.py.*--live"
if [ $? -eq 0 ]; then
    echo "   ✅ Atlas stopped"
else
    echo "   ℹ️  Atlas was not running"
fi

echo ""
echo "✅ All services stopped!"
echo "======================================================================"






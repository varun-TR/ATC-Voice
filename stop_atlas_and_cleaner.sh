#!/bin/bash
# Stop atlas.py and auto_cleaner.py

echo "======================================================================"
echo "🛑 Stopping ATC Atlas and Auto-Cleaner"
echo "======================================================================"

# Stop auto_cleaner
echo "🧹 Stopping auto-cleaner..."
pkill -f "auto_cleaner.py"
if [ $? -eq 0 ]; then
    echo "   ✅ Auto-cleaner stopped"
else
    echo "   ℹ️  Auto-cleaner was not running"
fi

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






#!/bin/bash

# Cleanup Memory Script for ATC Voice System
# Run this before starting the system if memory is low

echo "🧹 ATC Voice System Memory Cleanup"
echo "=================================="

# Kill any existing ATC processes
echo "1. Stopping all ATC services..."
pkill -f "python.*all_in_one.py" 2>/dev/null || true
pkill -f "python.*atlas.py" 2>/dev/null || true
pkill -f "python.*monitor_memory.py" 2>/dev/null || true
pkill -f "streamlit.*app.py" 2>/dev/null || true

# Wait for processes to die
sleep 3

echo "   ✅ All ATC services stopped"

# Show current memory
echo ""
echo "2. Current memory status:"
free -h | grep -E "Mem:|Swap:"

# Clear Python cache
echo ""
echo "3. Clearing Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Python cache cleared"

# Run Python garbage collection
echo ""
echo "4. Running Python garbage collection..."
python3 << EOF
import gc
gc.collect()
print("   ✅ Garbage collection complete")
EOF

# Clear temporary files
echo ""
echo "5. Clearing temporary files..."
rm -f temp_*.wav 2>/dev/null || true
rm -f temp_*.mp3 2>/dev/null || true
echo "   ✅ Temporary files cleared"

# Show memory after cleanup
echo ""
echo "6. Memory status after cleanup:"
free -h | grep -E "Mem:|Swap:"

echo ""
echo "=================================="
echo "✅ Memory cleanup complete!"
echo ""
echo "💡 Tips to improve memory:"
echo "   - Close unnecessary applications"
echo "   - Clear browser tabs"
echo "   - Restart if memory is still low"
echo "   - Add more swap space (see MEMORY_FIX_SUMMARY.md)"
echo ""
echo "Ready to start system? Run:"
echo "   ./run_live_system.sh"


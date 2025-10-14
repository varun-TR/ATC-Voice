#!/bin/bash

# ATC Voice Cleanup Script
# Removes unnecessary files and directories

echo "🧹 ATC Voice Cleanup Script"
echo "=========================="

cd /home/atc_voice/ATC-Voice

echo ""
echo "📁 Files and directories to be removed:"
echo "======================================="

# 1. Remove empty directories
echo "1. Empty directories:"
if [ -d "docs" ] && [ -z "$(ls -A docs)" ]; then
    echo "   - docs/ (empty)"
fi
if [ -d "notebooks" ] && [ -z "$(ls -A notebooks)" ]; then
    echo "   - notebooks/ (empty)"
fi
if [ -d "tests" ] && [ -z "$(ls -A tests)" ]; then
    echo "   - tests/ (empty)"
fi
if [ -d "src/utils" ] && [ -z "$(ls -A src/utils)" ]; then
    echo "   - src/utils/ (empty)"
fi

# 2. Remove temporary and log files
echo ""
echo "2. Temporary and log files:"
if [ -f "fix.txt" ]; then
    echo "   - fix.txt"
fi
if [ -f "nohup.out" ]; then
    echo "   - nohup.out"
fi
if [ -f "logs/postprocessing.log" ]; then
    echo "   - logs/postprocessing.log"
fi

# 3. Remove old audio files (keep only recent ones)
echo ""
echo "3. Old audio files (keeping only last 10):"
AUDIO_COUNT=$(find src/data/raw -name "*.wav" | wc -l)
if [ $AUDIO_COUNT -gt 10 ]; then
    echo "   - $((AUDIO_COUNT - 10)) old audio files"
fi

# 4. Remove unused scripts
echo ""
echo "4. Potentially unused scripts:"
if [ -f "run_dashboard_simple.sh" ]; then
    echo "   - run_dashboard_simple.sh (superseded by run_dashboard.sh)"
fi

# 5. Remove duplicate categorized file
echo ""
echo "5. Duplicate categorized file:"
if [ -f "src/data/logs/categorized/categorized_with_callsign.json" ]; then
    echo "   - src/data/logs/categorized/categorized_with_callsign.json (old location)"
fi

# 6. Remove duplicate ATC-Voice directory
echo ""
echo "6. Duplicate directory structure:"
if [ -d "ATC-Voice" ]; then
    echo "   - ATC-Voice/ (duplicate root directory)"
fi

echo ""
echo "⚠️  This will remove the above files and directories."
echo "Press Enter to continue or Ctrl+C to cancel..."
read

echo ""
echo "🗑️  Starting cleanup..."

# Remove empty directories
echo "Removing empty directories..."
[ -d "docs" ] && [ -z "$(ls -A docs)" ] && rmdir docs && echo "   ✅ Removed docs/"
[ -d "notebooks" ] && [ -z "$(ls -A notebooks)" ] && rmdir notebooks && echo "   ✅ Removed notebooks/"
[ -d "tests" ] && [ -z "$(ls -A tests)" ] && rmdir tests && echo "   ✅ Removed tests/"
[ -d "src/utils" ] && [ -z "$(ls -A src/utils)" ] && rmdir src/utils && echo "   ✅ Removed src/utils/"

# Remove temporary files
echo "Removing temporary files..."
[ -f "fix.txt" ] && rm fix.txt && echo "   ✅ Removed fix.txt"
[ -f "nohup.out" ] && rm nohup.out && echo "   ✅ Removed nohup.out"
[ -f "logs/postprocessing.log" ] && rm logs/postprocessing.log && echo "   ✅ Removed logs/postprocessing.log"

# Remove old audio files (keep only last 10)
echo "Cleaning up old audio files..."
if [ -d "src/data/raw" ]; then
    AUDIO_COUNT=$(find src/data/raw -name "*.wav" | wc -l)
    if [ $AUDIO_COUNT -gt 10 ]; then
        # Keep only the 10 most recent files
        find src/data/raw -name "*.wav" -type f -printf '%T@ %p\n' | sort -n | head -n -10 | cut -d' ' -f2- | xargs rm -f
        echo "   ✅ Removed $((AUDIO_COUNT - 10)) old audio files"
    else
        echo "   ℹ️  No old audio files to remove"
    fi
fi

# Remove unused scripts
echo "Removing unused scripts..."
[ -f "run_dashboard_simple.sh" ] && rm run_dashboard_simple.sh && echo "   ✅ Removed run_dashboard_simple.sh"

# Remove duplicate categorized file
echo "Removing duplicate categorized file..."
[ -f "src/data/logs/categorized/categorized_with_callsign.json" ] && rm src/data/logs/categorized/categorized_with_callsign.json && echo "   ✅ Removed old categorized file"
[ -d "src/data/logs/categorized" ] && [ -z "$(ls -A src/data/logs/categorized)" ] && rmdir src/data/logs/categorized && echo "   ✅ Removed empty categorized directory"

# Remove duplicate ATC-Voice directory
echo "Removing duplicate directory structure..."
if [ -d "ATC-Voice" ]; then
    rm -rf ATC-Voice && echo "   ✅ Removed duplicate ATC-Voice directory"
fi

# Clean up __pycache__ directories
echo "Cleaning up Python cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && echo "   ✅ Removed __pycache__ directories"

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📊 Current project structure:"
echo "============================="
tree -I 'venv' -L 3 2>/dev/null || find . -type d -not -path './venv*' | head -20

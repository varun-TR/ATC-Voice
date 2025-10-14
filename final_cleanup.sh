#!/bin/bash

# ATC Voice Final Cleanup - Remove Legacy Files
# This removes unused/legacy files that are no longer needed

echo "🧹 ATC Voice Final Cleanup - Legacy Files"
echo "========================================="

cd /home/atc_voice/ATC-Voice

echo ""
echo "📁 Legacy files to be removed:"
echo "==============================="

# Check for legacy speech-to-text files
if [ -d "src/speech_to_text" ]; then
    echo "1. Legacy speech-to-text files:"
    echo "   - src/speech_to_text/all_in_one.py (legacy transcription)"
    echo "   - src/speech_to_text/whisper.py (legacy transcription)"
fi

# Check for legacy audio extraction
if [ -f "src/data_ingestion/audioextraction.py" ]; then
    echo "2. Legacy audio extraction:"
    echo "   - src/data_ingestion/audioextraction.py (legacy audio processing)"
fi

# Check for cleanup script itself
if [ -f "cleanup.sh" ]; then
    echo "3. Cleanup script:"
    echo "   - cleanup.sh (no longer needed after cleanup)"
fi

echo ""
echo "⚠️  These appear to be legacy files not used in the current live system."
echo "The current live system uses:"
echo "   - logext.py (live communications detection)"
echo "   - postprocess.py (live categorization)"
echo "   - app.py (live dashboard)"
echo ""
echo "Press Enter to remove legacy files or Ctrl+C to cancel..."
read

echo ""
echo "🗑️  Removing legacy files..."

# Remove legacy speech-to-text files
if [ -d "src/speech_to_text" ]; then
    rm -rf src/speech_to_text
    echo "   ✅ Removed src/speech_to_text/ directory"
fi

# Remove legacy audio extraction
if [ -f "src/data_ingestion/audioextraction.py" ]; then
    rm src/data_ingestion/audioextraction.py
    echo "   ✅ Removed src/data_ingestion/audioextraction.py"
fi

# Remove cleanup script
if [ -f "cleanup.sh" ]; then
    rm cleanup.sh
    echo "   ✅ Removed cleanup.sh"
fi

echo ""
echo "✅ Final cleanup complete!"
echo ""
echo "📊 Current clean project structure:"
echo "==================================="
echo ""
echo "Essential files remaining:"
echo "  📁 config/ - Configuration files"
echo "  📁 src/"
echo "    📁 dashboard/ - Live dashboard (app.py)"
echo "    📁 data_ingestion/ - Live communications (logext.py)"
echo "    📁 nlp_analysis/ - Live categorization (postprocess.py)"
echo "    📁 data/logs/ - Live data files"
echo "  📁 venv/ - Python virtual environment"
echo "  📄 run_*.sh - Startup scripts"
echo "  📄 verify_data.sh - Data verification"
echo "  📄 LIVE_SYSTEM_README.md - Documentation"
echo ""
echo "🎯 Your ATC Voice system is now clean and optimized!"

#!/bin/bash

# GitHub Push Script with Authentication
cd /home/atc_voice/ATC-Voice

echo "🚀 Pushing ATC Voice Live System to GitHub..."
echo "Repository: https://github.com/varun-TR/ATC-Voice.git"
echo ""

# Check if we're already authenticated
if git ls-remote origin > /dev/null 2>&1; then
    echo "✅ Already authenticated, pushing changes..."
    git push origin main
else
    echo "🔐 Authentication required..."
    echo ""
    echo "Please provide your GitHub Personal Access Token when prompted."
    echo "If you don't have one, create it at: https://github.com/settings/tokens"
    echo "Required permissions: repo (Full control of private repositories)"
    echo ""
    
    # Try to push with manual authentication
    git push origin main
fi

echo ""
echo "✅ Push completed!"

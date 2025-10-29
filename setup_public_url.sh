#!/bin/bash

echo "======================================================================"
echo "🌐 Setting up Public URL for Dashboard"
echo "======================================================================"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "📦 Installing Node.js and npm..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Install localtunnel
echo "📦 Installing localtunnel..."
sudo npm install -g localtunnel

echo ""
echo "✅ Localtunnel installed!"
echo ""
echo "🚀 Creating public URL for dashboard..."
echo ""

# Start tunnel
lt --port 8501 --subdomain atc-dashboard


#!/bin/bash

echo "======================================================================"
echo "🌐 Setting up Cloudflare Tunnel for Dashboard"
echo "======================================================================"

# Install cloudflared
echo "📦 Installing cloudflared..."
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
rm cloudflared-linux-amd64.deb

echo ""
echo "✅ Cloudflared installed!"
echo ""
echo "🚀 Starting tunnel to dashboard on port 8501..."
echo ""
echo "This will generate a public URL that anyone can access!"
echo ""

# Start tunnel
cloudflared tunnel --url http://localhost:8501


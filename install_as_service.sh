#!/bin/bash

# Install ATC Voice as a systemd service (auto-starts on VM boot)

echo "======================================================================"
echo "🚀 Installing ATC Voice as System Service"
echo "======================================================================"

# Create systemd service file
sudo tee /etc/systemd/system/atc-voice.service << 'EOF'
[Unit]
Description=ATC Voice Live System
After=network.target

[Service]
Type=forking
User=stanjore
WorkingDirectory=/home/atc_voice/ATC-Voice
ExecStart=/home/atc_voice/ATC-Voice/run_live_system.sh
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/atc_voice/ATC-Voice/logs/service.log
StandardError=append:/home/atc_voice/ATC-Voice/logs/service.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "📋 Reloading systemd..."
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
echo "✅ Enabling auto-start on boot..."
sudo systemctl enable atc-voice.service

echo ""
echo "======================================================================"
echo "✅ ATC Voice Service Installed!"
echo "======================================================================"
echo ""
echo "📋 Service Commands:"
echo "  Start:   sudo systemctl start atc-voice"
echo "  Stop:    sudo systemctl stop atc-voice"
echo "  Restart: sudo systemctl restart atc-voice"
echo "  Status:  sudo systemctl status atc-voice"
echo "  Logs:    sudo journalctl -u atc-voice -f"
echo ""
echo "🔄 Auto-start enabled - Service will start automatically on VM boot!"
echo "======================================================================"






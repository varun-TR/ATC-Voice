#!/bin/bash
# Open port 8501 for dashboard access
echo "Opening port 8501 in firewall..."
sudo ufw allow 8501/tcp
sudo ufw status | grep 8501
echo "Port 8501 is now open!"

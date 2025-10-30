#!/bin/bash

echo "======================================================================"
echo "🌐 Setting up Nginx Reverse Proxy for Dashboard"
echo "======================================================================"

# Install nginx
echo "📦 Installing nginx..."
sudo apt-get update
sudo apt-get install -y nginx

# Create nginx configuration
echo "⚙️ Creating nginx configuration..."
sudo tee /etc/nginx/sites-available/atc-dashboard << 'EOF'
server {
    listen 80;
    listen [::]:80;
    
    server_name _;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    
    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/atc-dashboard /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo "🔍 Testing nginx configuration..."
sudo nginx -t

# Restart nginx
echo "🔄 Restarting nginx..."
sudo systemctl restart nginx
sudo systemctl enable nginx

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "======================================================================"
echo "✅ Nginx setup complete!"
echo "======================================================================"
echo ""
echo "📱 Access your dashboard at:"
echo "   http://${SERVER_IP}"
echo "   (Port 80 - standard HTTP, no port number needed!)"
echo ""
echo "🔧 Nginx status: sudo systemctl status nginx"
echo "📋 Nginx logs: sudo tail -f /var/log/nginx/access.log"
echo "======================================================================"





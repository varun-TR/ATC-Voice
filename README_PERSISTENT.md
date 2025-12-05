# Running ATC Voice System Persistently (After VPN Disconnect)

## 🎯 Problem
When you disconnect from VPN, processes started interactively may stop. This guide ensures the system keeps running.

## ✅ Solution Options

### Option 1: Use `start_persistent.sh` (Recommended)
```bash
./start_persistent.sh
```
- Starts system in background with `nohup`
- Saves PID to `.system_pid` file
- Continues running after VPN disconnect
- To stop: `./stop_system.sh`

### Option 2: Use Systemd Service (Best for Long-term)
```bash
# Start the service
sudo systemctl start atc-voice

# Check status
sudo systemctl status atc-voice

# Stop the service
sudo systemctl stop atc-voice

# View logs
sudo journalctl -u atc-voice -f
```
- Most robust - survives reboots and VPN disconnects
- Auto-restart on failure (if configured)
- Can enable auto-start on boot: `sudo systemctl enable atc-voice`

### Option 3: Use Screen/Tmux (For Interactive Monitoring)
```bash
# Install screen if needed
sudo apt-get install screen -y

# Start in screen session
screen -S atc-voice
./run_live_system.sh
# Press Ctrl+A then D to detach

# Reattach later
screen -r atc-voice
```

## 📋 Current Status

**Currently Running:**
- Check with: `ps aux | grep -E "(all_in_one|atlas|streamlit|logext)" | grep -v grep`

**To Start System:**
```bash
./start_persistent.sh
```

**To Stop System:**
```bash
./stop_system.sh
```

## 🔍 Monitoring

**Check if processes are running:**
```bash
ps aux | grep -E "(all_in_one|atlas|streamlit)" | grep -v grep
```

**View logs:**
```bash
tail -f logs/audio_recording.log
tail -f logs/atlas.log
tail -f logs/dashboard.log
tail -f logs/system_startup.log
```

## ⚠️ Important Notes

1. **VPN Disconnect**: Processes started with `start_persistent.sh` or systemd will continue running
2. **Manual Stop**: Use `stop_system.sh` or `sudo systemctl stop atc-voice` to stop
3. **logext.py**: This runs separately and persists independently
4. **Dashboard**: Accessible at `http://[VM_IP]:8501` even after VPN disconnect












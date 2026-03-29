# ATC Voice System - Quick Start Guide

## The Problem Was Fixed! 🎉

Your system was experiencing **Out-Of-Memory (OOM) kills** where the Linux kernel was terminating all services due to insufficient RAM. This has been **fixed** with:

1. ✅ Memory-optimized code with aggressive garbage collection
2. ✅ Reduced memory buffers
3. ✅ Memory monitoring system
4. ✅ Automatic service restart on crashes
5. ✅ Pre-flight memory checks

## How to Start the System

### Option 1: Quick Start (Recommended)
```bash
cd /home/atc_voice/ATC-Voice

# Clean up memory first
./cleanup_memory.sh

# Start all services
./run_live_system.sh
```

### Option 2: Check Memory First
```bash
cd /home/atc_voice/ATC-Voice

# Check available memory
free -h

# If available memory < 1GB, run cleanup first
./cleanup_memory.sh

# Start the system
./run_live_system.sh
```

## What's Running

When you start the system, the following services will run:

1. **Audio Recording** - Captures live ATC audio from LiveATC
2. **ATC Transcription** - Converts audio to text using specialized AI model
3. **Auto-Processing** - Categorizes and analyzes transcriptions
4. **Auto-Cleaner** - Removes unwanted text patterns
5. **Memory Monitor** - Watches for memory issues (NEW!)
6. **Dashboard** - Web interface at http://localhost:8501

## Auto-Restart Feature

The system now **automatically restarts** crashed services:
- Detects when services die
- Waits 30 seconds for stabilization
- Restarts failed services
- Up to 3 restart attempts
- Logs all restart events

## Monitoring

### Check System Status
```bash
# Watch all logs
tail -f logs/*.log

# Watch memory specifically
tail -f logs/memory_monitor.log

# Check current memory
free -h
```

### View Logs
- Audio: `logs/audio_recording.log`
- Processing: `logs/auto_processing.log`
- Cleaner: `logs/auto_cleaner.log`
- Memory: `logs/memory_monitor.log`
- Dashboard: `logs/dashboard.log`

## If Services Still Crash

### Step 1: Check Memory
```bash
free -h
```

If available memory < 500MB, you need more RAM or swap.

### Step 2: Add More Swap Space
```bash
# Create 4GB swap file (requires sudo)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make it permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
swapon --show
```

### Step 3: Reduce Memory Usage

Edit `src/utils/all_in_one.py` and set:
```python
START_DASHBOARD = False  # Line ~642
```

This disables the dashboard to save memory.

### Step 4: Check for Memory Leaks
```bash
# Monitor process memory over time
watch -n 5 'ps aux --sort=-%mem | head -10'
```

## Stopping the System

Press `Ctrl+C` in the terminal where you ran `./run_live_system.sh`

The script will gracefully stop all services.

## Tips for Best Performance

1. **Close other applications** before starting
2. **Don't run multiple instances** of the system
3. **Monitor memory regularly** using `free -h`
4. **Check logs** if services restart frequently
5. **Add swap space** if you have < 2GB swap
6. **Reboot** if memory doesn't free up

## Understanding Memory States

### 🟢 Healthy (Normal Operation)
- Available memory: > 1GB
- Swap usage: < 60%
- All services running smoothly

### 🟡 Warning (Watch Closely)
- Available memory: 500MB - 1GB  
- Swap usage: 60-80%
- System still functional but tight

### 🔴 Critical (May Crash)
- Available memory: < 500MB
- Swap usage: > 80%
- OOM killer may activate
- Services may crash and auto-restart

## Getting Help

1. **Read the detailed guide**: `MEMORY_FIX_SUMMARY.md`
2. **Check memory**: `free -h`
3. **Check logs**: `tail -f logs/*.log`
4. **Clean memory**: `./cleanup_memory.sh`
5. **Restart system**: Stop with Ctrl+C, then `./run_live_system.sh`

## Summary of Changes Made

### Code Changes
- `src/utils/all_in_one.py` - Memory optimizations
- `run_live_system.sh` - Auto-restart and monitoring

### New Files
- `monitor_memory.py` - Memory monitoring service
- `cleanup_memory.sh` - Memory cleanup helper
- `MEMORY_FIX_SUMMARY.md` - Detailed documentation
- `QUICK_START.md` - This file

### No Breaking Changes
All existing functionality preserved - your transcriptions, audio files, and settings are unchanged.

---

## Ready to Start?

```bash
./cleanup_memory.sh && ./run_live_system.sh
```

The system should now run stably without OOM crashes! 🚀


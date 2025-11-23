# ATC Voice System - Current Setup

## ✅ All Issues Fixed!

### What Was Fixed:
1. ✅ **OOM (Out-Of-Memory) crashes** - Fixed with memory optimizations
2. ✅ **Dashboard auto-restart disabled** - Now fully manual control
3. ✅ **Memory monitor disabled** - Removed as per user preference

---

## 🚀 Currently Running Services

### ✅ Active Services (Auto-restart enabled)
1. **Audio Recording & Transcription** 
   - Status: ✅ Running (PID varies)
   - Function: Records LiveATC stream and transcribes with AI
   - Auto-restart: YES (up to 3 times)

2. **Auto-Processing (Atlas)**
   - Status: ✅ Running (PID varies)
   - Function: Categorizes and analyzes transcriptions
   - Auto-restart: YES (up to 3 times)

3. **Auto-Cleaner**
   - Status: ✅ Running (PID varies)
   - Function: Removes unwanted text patterns
   - Auto-restart: YES (up to 3 times)

### ⏭️ Manual Services (No auto-restart)
4. **Dashboard**
   - Status: ⏭️ Manual control
   - Function: Web interface for monitoring
   - Auto-restart: NO
   - Start with: `./start_dashboard.sh`
   - Stop with: `pkill -f "streamlit.*app.py"`

### ❌ Disabled Services
5. **Memory Monitor**
   - Status: ❌ Disabled
   - Reason: User preference
   - To re-enable: Uncomment lines 173-181 in `run_live_system.sh`

---

## 📋 How to Use the System

### Starting the Full System
```bash
cd /home/atc_voice/ATC-Voice
./run_live_system.sh
```

This will start:
- ✅ Audio Recording & Transcription
- ✅ Auto-Processing
- ✅ Auto-Cleaner
- ⏭️ Dashboard (NOT started - manual control)
- ❌ Memory Monitor (disabled)

### Starting Dashboard Manually
```bash
./start_dashboard.sh
```

### Stopping Dashboard
```bash
pkill -f "streamlit.*app.py"
```

### Stopping Everything
Press `Ctrl+C` in the terminal where `run_live_system.sh` is running

---

## 🔧 Configuration Changes Made

### File: `run_live_system.sh`

1. **Dashboard Auto-Start**: DISABLED
   - Lines 183-215: Commented out automatic dashboard startup
   - Dashboard will NOT start when system starts

2. **Dashboard Auto-Restart**: DISABLED
   - Lines 408-412: Changed to skip dashboard restart
   - Dashboard will NOT restart if it crashes

3. **Memory Monitor**: DISABLED
   - Lines 171-181: Commented out memory monitor startup
   - Memory monitor will NOT start

### File: `src/utils/all_in_one.py`

1. **Memory Optimizations**: ACTIVE
   - Aggressive garbage collection
   - GPU memory clearing
   - Reduced buffer sizes
   - Immediate cleanup after transcriptions

### New Files Created

1. **`start_dashboard.sh`** - Manual dashboard starter
2. **`cleanup_memory.sh`** - Memory cleanup utility
3. **`monitor_memory.py`** - Memory monitor (disabled but available)
4. **`MEMORY_FIX_SUMMARY.md`** - Technical documentation
5. **`QUICK_START.md`** - User guide

---

## 📊 Current System Status

### Memory Usage (Typical)
- Audio/Transcription: ~4-7 GB (Whisper AI model)
- Auto-Processing: ~60-80 MB
- Auto-Cleaner: ~40-50 MB
- Dashboard (if started): ~60-80 MB

### Auto-Restart Policy
- **Enabled for**: Audio, Processing, Cleaner
- **Disabled for**: Dashboard, Memory Monitor
- **Max attempts**: 3 restarts per service
- **Wait time**: 30 seconds between restarts

---

## 🎯 Quick Commands

```bash
# Check what's running
ps aux | grep -E "python.*(all_in_one|atlas|auto_cleaner)" | grep -v grep

# Start dashboard
./start_dashboard.sh

# Stop dashboard
pkill -f "streamlit.*app.py"

# Clean up memory before starting
./cleanup_memory.sh

# Start full system
./run_live_system.sh

# Check memory usage
free -h

# View logs
tail -f logs/audio_recording.log
tail -f logs/auto_processing.log
tail -f logs/auto_cleaner.log
tail -f logs/dashboard.log
```

---

## ⚙️ To Re-Enable Disabled Features

### Re-enable Memory Monitor
Edit `run_live_system.sh` and uncomment lines 173-181:
```bash
# Remove the # from these lines:
# echo "🔍 Starting memory monitor..."
# if [ -f "monitor_memory.py" ]; then
#     nohup python3 monitor_memory.py > logs/memory_monitor.log 2>&1 &
#     MEMORY_MONITOR_PID=$!
#     echo "✅ Memory monitor started (PID: $MEMORY_MONITOR_PID)"
# else
#     echo "⚠️ Memory monitor script not found (monitor_memory.py)"
# fi
```

### Re-enable Dashboard Auto-Start
Edit `run_live_system.sh` and uncomment lines 196-215

### Re-enable Dashboard Auto-Restart
Edit `run_live_system.sh` lines 408-412 and restore the original code

---

## 📞 Support

If you encounter issues:
1. Check memory: `free -h`
2. Check running processes: `ps aux | grep python`
3. View logs: `tail -f logs/*.log`
4. Clean memory: `./cleanup_memory.sh`
5. Restart system: Stop with Ctrl+C, then `./run_live_system.sh`

---

**Last Updated**: 2025-11-15
**System Version**: Memory-optimized with manual dashboard control
**Status**: ✅ All working, OOM issue resolved


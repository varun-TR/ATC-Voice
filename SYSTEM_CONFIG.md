# ATC Voice System Configuration

**Last Updated**: November 15, 2025

---

## 🚀 Current Setup

### When you run `./run_live_system.sh`:

✅ **Auto-Start Services:**
1. **Audio Recording & Transcription** (all_in_one.py)
   - Using GPU acceleration (NVIDIA A40-8Q)
   - 10-15x faster than CPU
   - Recording from LiveATC stream
   
2. **Auto-Processing** (atlas.py)
   - Categorizes transcriptions
   - Updates categorized_transcription_results.json
   
3. **Auto-Cleaner** (auto_cleaner.py)
   - Removes unwanted text patterns
   
4. **Dashboard** (Streamlit)
   - ✅ NOW AUTO-STARTS!
   - Available at http://localhost:8501
   - External access: http://[SERVER_IP]:8501

---

## ⚙️ System Behavior

### Auto-Start: ✅ YES
- All 4 services start automatically with one command

### Auto-Restart: ❌ NO
- If a service crashes, it stays dead
- You need to manually restart by stopping and running `./run_live_system.sh` again

### Memory Monitor: ❌ DISABLED
- Not started (user preference)

---

## 📋 How to Use

### Start Everything (One Command):
```bash
./run_live_system.sh
```

This starts:
- ✅ Audio Recording (GPU-accelerated)
- ✅ Auto-Processing
- ✅ Auto-Cleaner
- ✅ Dashboard

### Stop Everything:
Press `Ctrl+C` in the terminal where you ran `run_live_system.sh`

Or manually kill:
```bash
pkill -f "run_live_system.sh"
pkill -f "all_in_one.py"
pkill -f "atlas.py"
pkill -f "auto_cleaner.py"
pkill -f "streamlit.*app.py"
```

### Start Dashboard Only (if needed separately):
```bash
./start_dashboard.sh
```

### Stop Dashboard Only:
```bash
pkill -f "streamlit.*app.py"
```

---

## 🖥️ GPU Configuration

### Status: ✅ ENABLED
- **Device**: NVIDIA A40-8Q
- **VRAM**: 8 GB
- **PyTorch**: 2.5.1+cu121 (CUDA 12.1)
- **Usage**: ~5-6 GB VRAM during transcription
- **Performance**: 10-15x faster than CPU

### Speed Comparison:
- **CPU**: 2-5 minutes per 30s audio
- **GPU**: ~5-15 seconds per 30s audio

---

## 📊 Typical Resource Usage

### With GPU:
- **GPU Memory**: 5-6 GB
- **System RAM**: 2-3 GB
- **CPU**: 30-40%
- **GPU Utilization**: 50-80% during transcription

### All Services Running:
- Audio + GPU: ~2-3 GB RAM
- Processing: ~60-80 MB
- Cleaner: ~40-50 MB
- Dashboard: ~60-80 MB
- **Total**: ~3-4 GB RAM

---

## 🔄 Services Overview

| Service | Auto-Start | Auto-Restart | GPU | Status |
|---------|------------|--------------|-----|--------|
| Audio Recording | ✅ Yes | ❌ No | ✅ Yes | Active |
| Auto-Processing | ✅ Yes | ❌ No | ❌ No | Active |
| Auto-Cleaner | ✅ Yes | ❌ No | ❌ No | Active |
| Dashboard | ✅ Yes | ❌ No | ❌ No | Active |
| Memory Monitor | ❌ No | ❌ No | ❌ No | Disabled |

---

## 📁 File Locations

### Logs:
- Audio: `logs/audio_recording.log`
- Processing: `logs/auto_processing.log`
- Cleaner: `logs/auto_cleaner.log`
- Dashboard: `logs/dashboard.log`

### Data:
- Raw Audio: `src/data/raw/*.wav`
- Transcripts: `src/data/logs/transcripts/transcripts.json`
- Categorized: `src/data/logs/transcripts/categorized_transcription_results.json`
- Communications: `src/data/logs/atc_communications.txt`

---

## 🎯 Quick Commands

```bash
# Start everything
./run_live_system.sh

# Check what's running
ps aux | grep -E "python.*(all_in_one|atlas|auto_cleaner)|streamlit" | grep -v grep

# Check GPU usage
nvidia-smi

# View logs
tail -f logs/audio_recording.log
tail -f logs/auto_processing.log
tail -f logs/dashboard.log

# Check memory
free -h

# Stop dashboard only
pkill -f "streamlit.*app.py"
```

---

## ✅ Changes Made Today

1. ✅ Fixed OOM (Out-Of-Memory) crashes with memory optimizations
2. ✅ Disabled auto-restart feature (manual control)
3. ✅ Disabled memory monitor (user preference)
4. ✅ Installed PyTorch with CUDA support
5. ✅ **Enabled GPU acceleration** (10-15x faster!)
6. ✅ **Re-enabled dashboard auto-start**

---

## 💡 Tips

1. Dashboard runs on port 8501 by default
2. If port is busy, it tries 8502 automatically
3. GPU transcription is much faster - backlog will clear quickly
4. No auto-restart means you have full control
5. All services stop cleanly with Ctrl+C

---

**System Status**: ✅ Fully Operational with GPU Acceleration


# ATC Voice Live Processing System

## Overview
The ATC Voice system now supports **live processing** for both communications detection and transcript categorization. The system automatically processes new data as it becomes available.

## Components

### 1. Live Communications Detection (`logext.py`)
- **Input**: LiveATC audio stream
- **Output**: `src/data/logs/atc_communications.txt`
- **Status**: ✅ Already live
- **Description**: Continuously monitors audio stream and logs communication detections

### 2. Live Transcript Processing (`postprocess.py`)
- **Input**: `src/data/logs/transcripts/transcription_results.json`
- **Output**: `src/data/logs/transcripts/categorized_transcription_results.json`
- **Status**: ✅ Now live with file monitoring
- **Description**: Automatically categorizes new transcripts and appends to existing data

### 3. Live Dashboard (`app.py`)
- **Input**: Both communication logs and categorized transcriptions
- **Output**: Real-time web dashboard
- **Status**: ✅ Updated for live data
- **Description**: Displays live data with auto-refresh every 30 seconds

## Key Features

### Append Mode Processing
- **No data loss**: New transcripts are appended to existing categorized data
- **Duplicate detection**: Prevents processing the same transcript twice
- **Incremental updates**: Only processes new/unprocessed transcripts

### File Monitoring
- **Real-time detection**: Uses `watchdog` library to monitor file changes
- **Automatic processing**: Triggers categorization when new transcripts are detected
- **Efficient**: Only processes new data, not entire dataset

### Live Dashboard Updates
- **Auto-refresh**: Updates every 30 seconds when enabled
- **Live indicators**: Shows real-time status of both data sources
- **Manual control**: Users can toggle auto-refresh on/off

## Usage

### Start Complete Live System
```bash
./run_live_system.sh
```
This starts both live postprocessing and the dashboard.

### Start Individual Components

#### Live Postprocessing Only
```bash
./run_live_postprocessing.sh
```

#### Dashboard Only
```bash
./run_dashboard.sh
```

#### Manual Postprocessing (One-time)
```bash
python src/nlp_analysis/postprocess.py
```

#### Live Postprocessing (Manual)
```bash
python src/nlp_analysis/postprocess.py --live
```

## File Structure
```
src/
├── data/
│   └── logs/
│       ├── atc_communications.txt                    # Live communications
│       └── transcripts/
│           ├── transcription_results.json           # Raw transcriptions
│           └── categorized_transcription_results.json # Live categorized data
├── dashboard/
│   └── app.py                                       # Live dashboard
├── data_ingestion/
│   └── logext.py                                    # Live communications
└── nlp_analysis/
    └── postprocess.py                               # Live categorization
```

## Data Flow
1. **Audio Stream** → `logext.py` → `atc_communications.txt`
2. **Raw Transcripts** → `postprocess.py` → `categorized_transcription_results.json`
3. **Both Files** → `app.py` → **Live Dashboard**

## Benefits
- ✅ **Real-time processing**: No manual intervention needed
- ✅ **Data preservation**: Append mode prevents data loss
- ✅ **Efficient**: Only processes new data
- ✅ **Scalable**: Handles continuous data streams
- ✅ **User-friendly**: Live dashboard with auto-refresh
- ✅ **Robust**: Error handling and recovery mechanisms

## Monitoring
- Check `logs/postprocessing.log` for postprocessing activity
- Dashboard shows live status indicators
- File timestamps indicate last updates
- Process monitoring available via system tools

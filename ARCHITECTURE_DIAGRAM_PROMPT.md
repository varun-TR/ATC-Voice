# ATC Voice System Architecture Diagram Prompt for Eraser

## System Overview
Create a comprehensive architecture diagram for an **ATC Voice Live Communications System** that processes real-time Air Traffic Control audio streams, transcribes them using AI models, performs NLP analysis, and visualizes results in a live dashboard.

## Core Components

### 1. Data Ingestion Layer
- **LiveATC Stream** (External Source)
  - HTTP audio stream: `http://d.liveatc.net/zbw_ron4`
  - MP3 format, continuous streaming
  - NY Center Sector 9, Westminster High frequency

- **logext.py** (Communication Detection Service)
  - Monitors audio stream for communication activity
  - Detects speech using dBFS threshold (-38 dB)
  - Outputs: `src/data/logs/atc_communications.txt`
  - Runs independently as background service

### 2. Audio Processing & Transcription Layer
- **all_in_one.py** (Unified Audio Recording & Transcription System)
  - **SlidingWindowAudioSplitter**:
    - Downloads audio stream continuously
    - Creates 30-second audio chunks with 5-second overlap
    - Saves WAV files to `src/data/raw/`
    - Filename format: `atc_sliding_XXX_HHMMSS-HHMMSS_YYYYMMDD_HHMMSS.wav`
  
  - **TranscriptionEngine**:
    - Uses ATC-specialized Whisper model: `jlvdoorn/whisper-large-v3-atco2-asr`
    - GPU-accelerated (NVIDIA A40-8Q) with CPU fallback
    - Processes audio chunks via file watcher
    - Outputs: `src/data/logs/transcripts/transcripts.json`
    - Format: JSON with chunk_number, audio_file_raw, raw_duration_s, timestamp_utc, raw_transcription

  - **File Watcher** (watchdog):
    - Monitors `src/data/raw/` for new WAV files
    - Automatically triggers transcription on file creation
    - Prevents duplicate processing

### 3. NLP Processing & Cleaning Layer
- **atlas.py** (Transcription Cleaner & Categorizer)
  - Monitors `transcripts.json` for new entries
  - **Cleaning Functions**:
    - Removes spam patterns ("thank you", "subscribe", copyright symbols)
    - Removes repeated patterns ("? ? ?", "uh uh uh")
    - Removes standalone "thank you" entries
    - Cleans whitespace and punctuation artifacts
  
  - **Categorization** (via postprocess.py):
    - Categorizes communications using FAA-approved keywords
    - Categories: Frequency Handoffs, Heading Vectors, Altitude Clearances, Emergency Declarations, Miscellaneous, General Communications
    - Uses `config/final_aviation_ultimate_with_emergency.json`
  
  - **Airline Detection**:
    - Detects airline callsigns (e.g., "American", "United", "Delta")
    - Detects General Aviation N-numbers (e.g., "N12345")
    - Uses `config/enhanced_airline_callsigns.json` and phonetic alphabet
  
  - **Duplicate Flagging**:
    - Identifies redundant transcriptions using text similarity
    - Sets `duplicate_flag` field
  
  - Outputs: `src/data/logs/transcripts/cleaned_transcripts.json`
  - Append mode: Only processes new chunk_numbers, preserves existing data

- **postprocess.py** (Core NLP Functions)
  - `categorize_communication()`: Keyword-based categorization
  - `detect_callsign()`: Airline and GA aircraft detection
  - `flag_duplicates()`: Duplicate detection using text normalization
  - `preprocess_transcript()`: Text normalization and cleaning
  - `load_unified_config()`: Loads category keywords and airline callsigns

### 4. Visualization & Dashboard Layer
- **app.py** (Streamlit Dashboard)
  - Real-time web dashboard (port 8501)
  - **Data Sources**:
    - Primary: `cleaned_transcripts.json` (all metrics and visualizations)
    - Secondary: `atc_communications.txt` (communication detection logs)
  
  - **Features**:
    - Overview Tab: Recent transcriptions, daily stats, top airlines, top GA aircraft
    - Category Analysis: Distribution charts, category breakdowns
    - Airline Analysis: Commercial airlines vs General Aviation, top aircraft
    - Pattern Analysis: Hourly patterns, day-of-week trends, time intervals
    - Advanced Analytics: Response times, forecasting, anomaly detection
  
  - **Visualizations**:
    - Plotly Express charts (bar, line, pie, scatter)
    - Interactive hover data with registration names
    - Real-time updates via cache TTL (3-10 seconds)

### 5. Configuration Layer
- **config/** directory:
  - `final_aviation_ultimate_with_emergency.json`: Unified category keywords and airline callsigns
  - `enhanced_aviation_keywords.json`: FAA-approved keywords for categorization
  - `enhanced_airline_callsigns.json`: Airline callsigns and aliases
  - `phonetic_alphabet.json`: Phonetic alphabet mappings (Alpha, Bravo, etc.)
  - `airline_nnumbers.json`: N-number to aircraft registration lookup

### 6. Process Orchestration Layer
- **run_live_system.sh** (Main Orchestrator)
  - Starts all services in background:
    1. `all_in_one.py` → Audio recording & transcription
    2. `atlas.py` → Cleaning & categorization
    3. `streamlit run app.py` → Dashboard
  - Manages PIDs and process monitoring
  - Handles cleanup on shutdown

- **start_persistent.sh** (Persistent Mode)
  - Uses `nohup` to run system detached from terminal
  - Ensures processes continue after VPN/SSH disconnect
  - Saves PID to `.system_pid` for easy stopping

- **stop_system.sh** (Shutdown Script)
  - Stops all processes gracefully
  - Kills processes by name and PID
  - Cleans up port bindings

## Data Flow Architecture

```
LiveATC Stream (HTTP MP3)
    │
    ├─→ logext.py ────────────────→ atc_communications.txt
    │   (Communication Detection)
    │
    └─→ all_in_one.py
        │
        ├─→ SlidingWindowAudioSplitter
        │   └─→ src/data/raw/*.wav (30s chunks)
        │
        └─→ TranscriptionEngine
            │   (Whisper Model: jlvdoorn/whisper-large-v3-atco2-asr)
            │   (GPU: NVIDIA A40-8Q)
            │
            └─→ transcripts.json
                │
                └─→ atlas.py (File Watcher)
                    │   (Cleaning, Categorization, Airline Detection)
                    │   (Uses postprocess.py functions)
                    │
                    └─→ cleaned_transcripts.json
                        │
                        └─→ app.py (Streamlit Dashboard)
                            └─→ Web UI (Port 8501)
```

## Technology Stack

### Core Technologies
- **Python 3.12**: Main programming language
- **Streamlit**: Web dashboard framework
- **Transformers (Hugging Face)**: Whisper model loading
- **PyTorch**: Deep learning framework (GPU acceleration)
- **watchdog**: File system monitoring
- **pydub**: Audio processing
- **librosa**: Audio analysis
- **pandas**: Data manipulation
- **plotly**: Interactive visualizations
- **requests**: HTTP streaming

### Infrastructure
- **Linux VM**: Ubuntu-based server
- **GPU**: NVIDIA A40-8Q (8GB VRAM)
- **Virtual Environment**: Python venv
- **Process Management**: nohup, systemd (optional)
- **Ports**: 8501 (dashboard), 8502 (fallback)

## File Structure

```
ATC-Voice/
├── src/
│   ├── data_ingestion/
│   │   └── logext.py                    # Communication detection
│   ├── utils/
│   │   └── all_in_one.py                 # Audio recording & transcription
│   ├── nlp_analysis/
│   │   ├── atlas.py                      # Cleaning & categorization
│   │   └── postprocess.py                # Core NLP functions
│   ├── dashboard/
│   │   └── app.py                        # Streamlit dashboard
│   └── data/
│       ├── logs/
│       │   ├── atc_communications.txt    # Communication logs
│       │   └── transcripts/
│       │       ├── transcripts.json     # Raw transcriptions
│       │       └── cleaned_transcripts.json  # Cleaned & categorized
│       └── raw/                           # Audio WAV files
├── config/
│   ├── final_aviation_ultimate_with_emergency.json
│   ├── enhanced_aviation_keywords.json
│   ├── enhanced_airline_callsigns.json
│   └── phonetic_alphabet.json
├── logs/                                 # System logs
├── run_live_system.sh                    # Main orchestrator
├── start_persistent.sh                   # Persistent mode
└── stop_system.sh                        # Shutdown script
```

## Process Flow

1. **System Startup** (`run_live_system.sh`):
   - Checks dependencies and virtual environment
   - Cleans up existing processes
   - Starts `all_in_one.py` in background (PID tracking)
   - Waits 5 seconds for initialization
   - Starts `atlas.py` in background
   - Starts Streamlit dashboard on port 8501
   - Monitors all processes (no auto-restart)

2. **Audio Processing** (`all_in_one.py`):
   - Connects to LiveATC stream
   - Buffers audio in sliding window (30s chunks, 5s overlap)
   - Saves WAV files to `src/data/raw/`
   - File watcher detects new files
   - TranscriptionEngine loads Whisper model (GPU if available)
   - Transcribes each chunk and appends to `transcripts.json`

3. **NLP Processing** (`atlas.py`):
   - File watcher monitors `transcripts.json` for changes
   - Loads existing `cleaned_transcripts.json` (append mode)
   - Processes only new chunk_numbers
   - Cleans text (removes spam, patterns, copyright)
   - Categorizes using keywords from config
   - Detects airline callsigns and GA N-numbers
   - Flags duplicates
   - Appends to `cleaned_transcripts.json`

4. **Dashboard** (`app.py`):
   - Loads `cleaned_transcripts.json` and `atc_communications.txt`
   - Caches data with TTL (3-10 seconds)
   - Renders interactive visualizations
   - Updates automatically on cache expiry
   - Manual refresh button available

## Key Design Patterns

- **Append-Only Processing**: New data appended, never overwritten
- **File Watcher Pattern**: Automatic processing on file changes
- **Sliding Window**: Overlapping audio chunks for better transcription
- **Cache with TTL**: Dashboard updates without manual refresh
- **Process Orchestration**: Shell scripts manage lifecycle
- **Persistent Mode**: nohup ensures processes survive disconnection

## Diagram Requirements

Create a diagram showing:
1. **External Data Sources**: LiveATC stream
2. **Ingestion Layer**: logext.py, all_in_one.py
3. **Processing Pipeline**: Audio → Transcription → NLP → Cleaning
4. **Storage Layer**: JSON files, WAV files, text logs
5. **Visualization Layer**: Streamlit dashboard
6. **Configuration**: JSON config files
7. **Orchestration**: Shell scripts and process management
8. **Data Flow Arrows**: Show direction and format of data
9. **Technology Labels**: Whisper model, GPU, Python libraries
10. **Port Numbers**: Dashboard ports (8501, 8502)

Use different colors/shapes for:
- External services (cloud/rounded)
- Python scripts (rectangles)
- Data files (cylinders/databases)
- Configuration (documents)
- Processes/services (rounded rectangles)

Include annotations for:
- File formats (JSON, WAV, TXT)
- Model names (Whisper, jlvdoorn/whisper-large-v3-atco2-asr)
- Ports (8501, 8502)
- Key technologies (GPU, Streamlit, watchdog)


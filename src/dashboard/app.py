import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import re
import time
import shutil
import psutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

# Set page config
st.set_page_config(
    page_title="ATC Voice Communications Dashboard",
    page_icon="🛫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
BASE_DIR = Path(".")
TRANSCRIPTIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "transcripts" / "categorized_transcription_results.json"
COMMUNICATIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "atc_communications.txt"
AIRLINE_CALLSIGN_FILE = BASE_DIR / "config" / "airline_callsign.json"
PHONETIC_ALPHABET_FILE = BASE_DIR / "config" / "phonetic_alphabet.json"

# ----------------------------- Airline Detection Logic ----------------------------- #
@st.cache_resource
def load_airline_configs():
    """Load airline callsign and phonetic alphabet configs."""
    try:
        with open(AIRLINE_CALLSIGN_FILE, 'r', encoding='utf-8') as f:
            airline_data = json.load(f)
        
        with open(PHONETIC_ALPHABET_FILE, 'r', encoding='utf-8') as f:
            phonetic_data = json.load(f)
        
        # Flatten airline callsigns
        callsigns = {}
        for airline, aliases in airline_data.items():
            for alias in aliases:
                callsigns[alias.lower()] = airline
        
        return callsigns, phonetic_data
    except Exception as e:
        st.error(f"Error loading airline configs: {e}")
        return {}, {}

def words_to_digits(word: str) -> str:
    """Convert spelled numbers to digits."""
    mapping = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
    }
    return mapping.get(word, word)

def normalize_numbers(tokens: List[str]) -> List[str]:
    """Convert spelled numbers in list of tokens to digits."""
    return [words_to_digits(tok) for tok in tokens]

def preprocess_transcript_airline(text: str) -> str:
    """Normalize transcript for airline matching."""
    if not text or text.strip() == "":
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_airline_callsign(text: str, callsigns: Dict[str, str], phonetic_dict: Dict[str, str]) -> str:
    """Detect airline or general aviation callsign using enhanced logic."""
    if not text:
        return "Unknown"

    t = preprocess_transcript_airline(text)

    # ---  General Aviation Tail Number Detection ---
    # Check for direct N-numbers (e.g., N5194, N2905X)
    direct_match = re.search(r"\bN\d{1,5}[A-Z]{0,2}\b", text.upper())
    if direct_match:
        return f"General Aviation ({direct_match.group(0)})"

    # Decode phonetic GA sequences like "November six seven alpha foxtrot"
    ga_match = re.search(r"\bnovember[\s\-a-z0-9]+\b", t)
    if ga_match:
        phrase = ga_match.group(0)
        tokens = re.split(r"[\s\-]+", phrase.strip())
        tokens = normalize_numbers(tokens)

        tail = "N"
        for token in tokens[1:]:
            if token in phonetic_dict:
                tail += phonetic_dict[token]
            elif token.isdigit():
                tail += token
            elif len(token) == 1 and token.isalpha():
                tail += token.upper()

        tail = re.sub(r"[^A-Z0-9]", "", tail)

        # FAA format validation: N + 1–5 digits + 0–2 letters
        if re.match(r"^N\d{1,5}[A-Z]{0,2}$", tail):
            return f"General Aviation ({tail})"

    # --- Airline Callsign Detection (after GA check) ---
    for alias, airline in callsigns.items():
        if re.search(rf"\b{re.escape(alias.lower())}\b", t):
            # --- Handle ambiguous cases like "delta" ---
            if alias.lower() == "delta":
                # Skip if it's part of a GA phrase (e.g., November 23 Delta)
                if re.search(r"\bnovember\b", t):
                    continue

                # If "delta" is used with phonetic-like patterns, treat as GA
                if re.search(r"\bdelta (alpha|bravo|charlie|delta|echo|foxtrot|golf|hotel|india|juliet|kilo|lima|mike|november|oscar|papa|quebec|romeo|sierra|tango|uniform|victor|whiskey|xray|yankee|zulu)\b", t):
                    continue

                # If it's followed by a valid flight number (digits or spoken digits)
                if re.search(r"\bdelta (\d+|one|two|three|four|five|six|seven|eight|nine|zero)\b", t):
                    return airline

                # Otherwise, likely not an airline call
                continue

            # For all other aliases
            return airline

    return "Unknown"

@st.cache_data(ttl=5)  # Reduced cache to 5 seconds for better live updates
def load_transcription_data() -> Optional[pd.DataFrame]:
    """Load and parse transcription data from JSON file."""
    try:
        if not TRANSCRIPTIONS_FILE.exists():
            return None
        
        with open(TRANSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Handle corrupted JSON with extra data after closing brace
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Try to extract valid JSON by finding the first complete object
            if "Extra data" in str(e):
                # Find the position of the error and truncate
                try:
                    # Try to find the last valid closing brace before error position
                    valid_json = content[:e.pos].rstrip()
                    # Find the last complete JSON object
                    brace_count = 0
                    last_valid_pos = 0
                    for i, char in enumerate(valid_json):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                last_valid_pos = i + 1
                    
                    if last_valid_pos > 0:
                        valid_json = content[:last_valid_pos]
                        data = json.loads(valid_json)
                        st.warning("⚠️ Detected corrupted JSON file. Loaded valid data up to corruption point. The system will repair it on next update.")
                    else:
                        raise e
                except:
                    raise e
            else:
                raise e
        
        if 'items' not in data:
            return None
        
        df = pd.DataFrame(data['items'])
        
        # Convert timestamp to datetime
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
        df['date'] = df['timestamp_utc'].dt.date
        df['hour'] = df['timestamp_utc'].dt.hour
        df['day_of_week'] = df['timestamp_utc'].dt.day_name()
        
        # Extract flight number from transcription text
        df['flight_number'] = df['raw_transcription'].apply(extract_flight_number)
        
        # Re-detect airlines using enhanced logic
        callsigns, phonetic_dict = load_airline_configs()
        if callsigns:  # Only if configs loaded successfully
            df['airline_detected'] = df['raw_transcription'].apply(
                lambda text: detect_airline_callsign(text, callsigns, phonetic_dict)
            )
            # Use detected airline, fall back to original if detection fails
            df['airline'] = df['airline_detected'].fillna(df.get('airline', 'Unknown'))
        
        return df
    
    except Exception as e:
        st.error(f"Error loading transcription data: {e}")
        return None

@st.cache_data(ttl=5)  # Reduced cache to 5 seconds for better live updates
def load_communication_logs() -> Optional[pd.DataFrame]:
    """Load and parse communication detection logs."""
    try:
        if not COMMUNICATIONS_FILE.exists():
            return None
        
        with open(COMMUNICATIONS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse log entries
        log_entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse timestamp and message
            if line.startswith('[') and ']' in line:
                timestamp_str = line[1:line.find(']')]
                message = line[line.find(']') + 2:]
                
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Only include communication detection entries
                    if 'Communication detected' in message:
                        # Extract dBFS value
                        dbfs_match = re.search(r'\(dBFS: ([-\d.]+)\)', message)
                        dbfs = float(dbfs_match.group(1)) if dbfs_match else None
                        
                        log_entries.append({
                            'timestamp': timestamp,
                            'message': message,
                            'dbfs': dbfs,
                            'date': timestamp.date(),
                            'hour': timestamp.hour,
                            'day_of_week': timestamp.strftime('%A')
                        })
                
                except ValueError:
                    continue
        
        if not log_entries:
            return None
        
        return pd.DataFrame(log_entries)
    
    except Exception as e:
        st.error(f"Error loading communication logs: {e}")
        return None

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_disk_usage():
    """Get disk usage information for the VM."""
    try:
        # Get disk usage for the root directory
        disk_usage = shutil.disk_usage('/')
        
        # Convert bytes to GB
        total_gb = disk_usage.total / (1024**3)
        used_gb = disk_usage.used / (1024**3)
        free_gb = disk_usage.free / (1024**3)
        
        # Calculate percentage
        used_percent = (used_gb / total_gb) * 100
        free_percent = (free_gb / total_gb) * 100
        
        return {
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'used_percent': round(used_percent, 1),
            'free_percent': round(free_percent, 1)
        }
    except Exception as e:
        return {
            'total_gb': 0,
            'used_gb': 0,
            'free_gb': 0,
            'used_percent': 0,
            'free_percent': 0,
            'error': str(e)
        }


@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_audio_file_stats():
    """Get audio file statistics from the raw directory."""
    try:
        raw_dir = BASE_DIR / "src" / "data" / "raw"
        
        if not raw_dir.exists():
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'avg_size_mb': 0,
                'error': 'Raw audio directory not found'
            }
        
        # Get all audio files
        audio_files = list(raw_dir.glob("*.wav"))
        
        if not audio_files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'avg_size_mb': 0,
                'error': 'No audio files found'
            }
        
        # Calculate total size
        total_size_bytes = sum(f.stat().st_size for f in audio_files)
        total_size_mb = total_size_bytes / (1024 * 1024)
        avg_size_mb = total_size_mb / len(audio_files)
        
        return {
            'total_files': len(audio_files),
            'total_size_mb': round(total_size_mb, 2),
            'avg_size_mb': round(avg_size_mb, 2)
        }
    except Exception as e:
        return {
            'total_files': 0,
            'total_size_mb': 0,
            'avg_size_mb': 0,
            'error': str(e)
        }

@st.cache_data(ttl=10)  # Cache for 10 seconds - CPU changes frequently
def get_system_info():
    """Get system resource information."""
    try:
        # CPU usage - reduce interval to 0.1 seconds for faster response
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)
        memory_percent = memory.percent
        
        return {
            'cpu_percent': round(cpu_percent, 1),
            'memory_total_gb': round(memory_total_gb, 2),
            'memory_used_gb': round(memory_used_gb, 2),
            'memory_percent': round(memory_percent, 1)
        }
    except Exception as e:
        return {
            'cpu_percent': 0,
            'memory_total_gb': 0,
            'memory_used_gb': 0,
            'memory_percent': 0,
            'error': str(e)
        }


def clean_transcription_text(text: str) -> str:
    """Remove copyright notices and other artifacts from transcription text."""
    if not text:
        return ""
    
    # Remove anything after © symbol
    if '©' in text:
        text = text.split('©')[0]
    
    # Strip extra whitespace
    text = text.strip()
    
    return text

def extract_flight_number(text: str) -> str:
    if not text:
        return "Unknown"
    
    # Common flight number patterns
    patterns = [
        r'\b([A-Z]{2,3})\s*(\d{3,4})\b',  # AA1234, DL567
        r'\b([A-Z]+\d{2,4})\b',           # United1993
        r'\b(\d{3,4})\b'                  # Just numbers
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return "Unknown"

@st.cache_data(ttl=5)  # Reduced cache to 5 seconds for live updates
def calculate_advanced_comm_stats(communication_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Calculate advanced communication statistics from the notebook logic."""
    stats = {
        'signal_level_stats': {},
        'duration_stats': {},
        'time_range': {},
        'hourly_pattern_est': {}
    }
    
    if communication_df is None or communication_df.empty:
        return stats
    
    # Signal Level (dBFS) Statistics
    if 'dbfs' in communication_df.columns:
        dbfs_series = communication_df['dbfs'].dropna()
        if len(dbfs_series) > 0:
            stats['signal_level_stats'] = {
                'min': float(np.nanmin(dbfs_series)),
                'median': float(np.nanmedian(dbfs_series)),
                'mean': float(np.nanmean(dbfs_series)),
                'std': float(np.nanstd(dbfs_series, ddof=1)),
                'max': float(np.nanmax(dbfs_series))
            }
    
    # Communication Duration (inter-arrival times)
    if 'timestamp' in communication_df.columns:
        sorted_df = communication_df.sort_values('timestamp').copy()
        sorted_df['delta_s'] = sorted_df['timestamp'].diff().dt.total_seconds()
        
        duration_series = sorted_df['delta_s'].dropna()
        if len(duration_series) > 0:
            stats['duration_stats'] = {
                'min': float(np.nanmin(duration_series)),
                'median': float(np.nanmedian(duration_series)),
                'mean': float(np.nanmean(duration_series)),
                'std': float(np.nanstd(duration_series, ddof=1)),
                'max': float(np.nanmax(duration_series))
            }
        
        # Time Range
        timestamps = sorted_df['timestamp'].dropna()
        if len(timestamps) > 0:
            first_comm = timestamps.min()
            last_comm = timestamps.max()
            total_duration = last_comm - first_comm
            
            stats['time_range'] = {
                'first_communication': first_comm,
                'last_communication': last_comm,
                'total_duration': total_duration,
                'total_days': total_duration.days,
                'total_hours': total_duration.total_seconds() / 3600
            }
    
    # Hourly Pattern in EST (using UTC-5 offset)
    if 'timestamp' in communication_df.columns:
        df_copy = communication_df.copy()
        # Convert to EST by subtracting 5 hours from UTC
        df_copy['timestamp_est'] = pd.to_datetime(df_copy['timestamp']) - pd.Timedelta(hours=5)
        df_copy['hour_est'] = df_copy['timestamp_est'].dt.hour
        
        hourly_counts = df_copy.groupby('hour_est').size()
        stats['hourly_pattern_est'] = hourly_counts.to_dict()
    
    return stats

@st.cache_data(ttl=5)  # Reduced cache to 5 seconds for live updates
def calculate_stats(transcription_df: Optional[pd.DataFrame], communication_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Calculate statistics from both data sources."""
    stats = {
        'total_transcriptions': 0,
        'total_communications': 0,
        'categories': {},
        'daily_transcriptions': {},
        'daily_communications': {},
        'daily_category_counts': {},  # New: daily counts by category
        'hourly_pattern': {},
        'flight_stats': {
            'total_flights': 0,
            'avg_comms_per_flight': 0,
            'max_comms_per_flight': 0
        },
        'duration_stats': {},
        'airline_stats': {},  # New: airline counts
        'last_update': datetime.now()
    }
    
    # Transcription statistics
    if transcription_df is not None and not transcription_df.empty:
        stats['total_transcriptions'] = len(transcription_df)
        stats['categories'] = transcription_df['category'].value_counts().to_dict()
        stats['daily_transcriptions'] = transcription_df.groupby('date').size().to_dict()
        stats['hourly_pattern'] = transcription_df.groupby('hour').size().to_dict()
        
        # Calculate daily counts by category
        daily_category_groups = transcription_df.groupby(['date', 'category']).size()
        stats['daily_category_counts'] = {}
        for (date, category), count in daily_category_groups.items():
            if category not in stats['daily_category_counts']:
                stats['daily_category_counts'][category] = {}
            stats['daily_category_counts'][category][str(date)] = count
        
        # Airline statistics
        if 'airline' in transcription_df.columns:
            stats['airline_stats'] = transcription_df['airline'].value_counts().to_dict()
        
        # Flight statistics
        flight_counts = transcription_df['flight_number'].value_counts()
        stats['flight_stats'] = {
            'total_flights': flight_counts.nunique(),
            'avg_comms_per_flight': flight_counts.mean() if len(flight_counts) > 0 else 0,
            'max_comms_per_flight': flight_counts.max() if len(flight_counts) > 0 else 0
        }
        
        # Duration statistics
        if 'raw_duration_s' in transcription_df.columns:
            duration_series = transcription_df['raw_duration_s']
            stats['duration_stats'] = {
                'mean': duration_series.mean(),
                'median': duration_series.median(),
                'min': duration_series.min(),
                'max': duration_series.max(),
                'std': duration_series.std()
            }
    
    # Communication detection statistics
    if communication_df is not None and not communication_df.empty:
        stats['total_communications'] = len(communication_df)
        stats['daily_communications'] = communication_df.groupby('date').size().to_dict()
        
        # Audio level statistics
        if 'dbfs' in communication_df.columns:
            dbfs_series = communication_df['dbfs'].dropna()
            if len(dbfs_series) > 0:
                stats['audio_levels'] = {
                    'mean': dbfs_series.mean(),
                    'median': dbfs_series.median(),
                    'min': dbfs_series.min(),
                    'max': dbfs_series.max()
                }
    
    return stats

def main():
    st.title("🛫 ATC Voice Communications Dashboard")
    st.markdown("---")
    
    # Auto-refresh for live data
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh Communications", value=True, help="Automatically refresh communication data every 10 seconds")
    
    # Initialize session state for refresh timing
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    if auto_refresh:
        st.sidebar.info("🟢 Live monitoring active")
        current_time = time.time()
        time_since_refresh = current_time - st.session_state.last_refresh
        
        # Show countdown
        time_until_refresh = 10 - (time_since_refresh % 10)
        st.sidebar.info(f"Next refresh in: {int(time_until_refresh)}s")
        
        # Auto-refresh every 10 seconds using st.rerun
        if time_since_refresh >= 10:
            st.session_state.last_refresh = current_time
            st.sidebar.success("🔄 Refreshing data...")
            st.rerun()
    
    # Sidebar with data status
    st.sidebar.header("📊 Data Status")
    
    # Data source indicators
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if TRANSCRIPTIONS_FILE.exists():
            if auto_refresh:
                st.success(f"📝 Transcriptions: {TRANSCRIPTIONS_FILE.name}")
                st.caption("🟢 Live processing")
            else:
                st.info(f"📝 Transcriptions: {TRANSCRIPTIONS_FILE.name}")
                st.caption("⏸️ Manual refresh")
        else:
            st.error("📝 No transcription data")
    
    with col2:
        if COMMUNICATIONS_FILE.exists():
            if auto_refresh:
                st.success(f"🎙️ Communications: {COMMUNICATIONS_FILE.name}")
                st.caption("🟢 Live data")
            else:
                st.info(f"🎙️ Communications: {COMMUNICATIONS_FILE.name}")
                st.caption("⏸️ Manual refresh")
        else:
            st.error("🎙️ No communication logs")
    
    # Load data
    with st.spinner("Loading ATC data..."):
        transcription_df = load_transcription_data()
        communication_df = load_communication_logs()
    
    # Calculate statistics
    stats = calculate_stats(transcription_df, communication_df)
    advanced_stats = calculate_advanced_comm_stats(communication_df)
    
    st.sidebar.markdown(f"**Last Update:** {stats['last_update'].strftime('%H:%M:%S')}")
    
    # VM System Monitoring
    st.sidebar.markdown("---")
    st.sidebar.header("🖥️ VM System Status")
    
    # Get system information
    disk_info = get_disk_usage()
    system_info = get_system_info()
    audio_stats = get_audio_file_stats()
    
    # Disk space monitoring
    st.sidebar.subheader("💾 Disk Space")
    if 'error' not in disk_info:
        st.sidebar.metric(
            "Used Space", 
            f"{disk_info['used_gb']:.1f} GB",
            delta=f"{disk_info['used_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Free Space", 
            f"{disk_info['free_gb']:.1f} GB",
            delta=f"{disk_info['free_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Total Space", 
            f"{disk_info['total_gb']:.1f} GB"
        )
        
        # Disk usage progress bar
        disk_usage_percent = disk_info['used_percent']
        if disk_usage_percent > 90:
            st.sidebar.error(f"⚠️ Disk usage: {disk_usage_percent:.1f}%")
        elif disk_usage_percent > 80:
            st.sidebar.warning(f"⚠️ Disk usage: {disk_usage_percent:.1f}%")
        else:
            st.sidebar.success(f"✅ Disk usage: {disk_usage_percent:.1f}%")
    else:
        st.sidebar.error(f"❌ Disk info error: {disk_info['error']}")
    
    # System resources
    st.sidebar.subheader("⚡ System Resources")
    if 'error' not in system_info:
        st.sidebar.metric(
            "CPU Usage", 
            f"{system_info['cpu_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Memory Usage", 
            f"{system_info['memory_used_gb']:.1f} GB",
            delta=f"{system_info['memory_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Total Memory", 
            f"{system_info['memory_total_gb']:.1f} GB"
        )
    else:
        st.sidebar.error(f"❌ System info error: {system_info['error']}")
    
    # Audio file statistics
    st.sidebar.subheader("🎵 Audio Files")
    if 'error' not in audio_stats:
        st.sidebar.metric(
            "Total Audio Files", 
            f"{audio_stats['total_files']:,}"
        )
        st.sidebar.metric(
            "Total Audio Size", 
            f"{audio_stats['total_size_mb']:.1f} MB"
        )
        st.sidebar.metric(
            "Avg File Size", 
            f"{audio_stats['avg_size_mb']:.1f} MB"
        )
    else:
        st.sidebar.error(f"❌ Audio stats error: {audio_stats['error']}")
    
    # Show data source file info
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Sources:**")
    st.sidebar.code(f"Transcriptions:\n{TRANSCRIPTIONS_FILE}")
    st.sidebar.code(f"Communications:\n{COMMUNICATIONS_FILE}")
    
    # Main dashboard
    if transcription_df is None and communication_df is None:
        st.warning("⚠️ No data available. Please ensure the data files exist and contain valid data.")
        return
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", 
        "📈 Daily Analytics", 
        "🏷️ Categories",
        "📋 Detailed Stats", 
        "🔍 Pattern Analysis"
    ])
    
    with tab1:
        st.header("Dashboard Overview")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if auto_refresh:
                st.metric(
                    "Total Transcriptions", 
                    f"{stats['total_transcriptions']:,}",
                    delta=f"🟢 Live processing"
                )
            else:
                st.metric(
                    "Total Transcriptions", 
                    f"{stats['total_transcriptions']:,}",
                    delta=f"⏸️ Manual refresh"
                )
        
        with col2:
            if auto_refresh:
                st.metric(
                    "Communication Detections",
                    f"{stats['total_communications']:,}",
                    delta=f"🟢 Live monitoring"
                )
            else:
                st.metric(
                    "Communication Detections",
                    f"{stats['total_communications']:,}",
                    delta=f"⏸️ Manual refresh"
                )
        
        with col3:
            if stats['flight_stats']['total_flights'] > 0:
                st.metric(
                    "Unique Flights",
                    f"{stats['flight_stats']['total_flights']:,}",
                    delta=f"{stats['flight_stats']['avg_comms_per_flight']:.1f} avg/flight"
                )
            else:
                st.metric("Unique Flights", "0", delta="No data")
        
        with col4:
            if stats['categories']:
                top_category = max(stats['categories'], key=stats['categories'].get)
                st.metric(
                    "Top Category",
                    top_category,
                    delta=f"{stats['categories'][top_category]} comms"
                )
            else:
                st.metric("Top Category", "N/A", delta="No data")
        
        # Daily Communication Bar Graph
        st.subheader("📊 Daily Communication Counts")
        
        # Create daily data (only communication detections)
        daily_data = []
        
        if stats['daily_communications']:
            for date_str, count in stats['daily_communications'].items():
                daily_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Count': count
                })
        
        if daily_data:
            daily_df = pd.DataFrame(daily_data)
            
            # Create bar graph
            fig_daily_bar = px.bar(
                daily_df, 
                x='Date', 
                y='Count',
                title="Daily Communication Counts",
                labels={'Date': 'Date', 'Count': 'Number of Communications'},
                color_discrete_sequence=['#ff7f0e']
            )
            
            # Format x-axis to show dates properly
            fig_daily_bar.update_xaxes(
                tickformat="%Y-%m-%d",
                tickangle=45
            )
            
            # Update layout
            fig_daily_bar.update_layout(
                height=500,
                showlegend=False
            )
            
            st.plotly_chart(fig_daily_bar, use_container_width=True)
        else:
            st.info("No daily communication data available yet.")
        
        # Airline statistics section
        if stats['airline_stats']:
            if auto_refresh:
                st.subheader("✈️ Flight/Airline Statistics 🟢 Live")
            else:
                st.subheader("✈️ Flight/Airline Statistics")
            
            # Display airline counts as a table
            airline_df = pd.DataFrame(list(stats['airline_stats'].items()), 
                                    columns=['Airline/Flight', 'Count'])
            
            # Separate commercial airlines from general aviation
            airline_df['Type'] = airline_df['Airline/Flight'].apply(
                lambda x: 'General Aviation' if 'General Aviation' in str(x) else 'Commercial'
            )
            
            # Filter out "Unknown" entries
            known_df = airline_df[airline_df['Airline/Flight'] != 'Unknown'].copy()
            unknown_count = airline_df[airline_df['Airline/Flight'] == 'Unknown']['Count'].sum()
            
            if not known_df.empty:
                known_df = known_df.sort_values('Count', ascending=False)
                
                # Add percentage column
                total_known = known_df['Count'].sum()
                known_df['Percentage'] = (known_df['Count'] / total_known * 100).round(1)
                known_df['Percentage'] = known_df['Percentage'].astype(str) + '%'
                
                # Split into commercial and GA
                commercial_df = known_df[known_df['Type'] == 'Commercial'].copy()
                ga_df = known_df[known_df['Type'] == 'General Aviation'].copy()
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🛫 Commercial Airlines", len(commercial_df), 
                             delta=f"{commercial_df['Count'].sum()} comms")
                with col2:
                    st.metric("🛩️ General Aviation", len(ga_df), 
                             delta=f"{ga_df['Count'].sum()} comms")
                with col3:
                    st.metric("❓ Unknown", "—", delta=f"{unknown_count} comms" if unknown_count > 0 else "0 comms")
                
                # Create tabs for different views
                airline_tab1, airline_tab2, airline_tab3 = st.tabs([
                    "🛫 Commercial Airlines", 
                    "🛩️ General Aviation",
                    "📊 All Traffic"
                ])
                
                with airline_tab1:
                    if not commercial_df.empty:
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            display_commercial = commercial_df[['Airline/Flight', 'Count', 'Percentage']].head(20)
                            st.dataframe(display_commercial, use_container_width=True, hide_index=True, height=400)
                        with col2:
                            top_commercial = commercial_df.head(15)
                            fig_commercial = px.bar(
                                top_commercial, 
                                x='Airline/Flight', 
                                y='Count',
                                title="Top 15 Commercial Airlines",
                                labels={'Airline/Flight': 'Airline', 'Count': 'Communications'},
                                color='Count',
                                color_continuous_scale='Blues'
                            )
                            fig_commercial.update_layout(height=400, xaxis_tickangle=45, showlegend=False)
                            st.plotly_chart(fig_commercial, use_container_width=True)
                    else:
                        st.info("No commercial airline communications detected yet.")
                
                with airline_tab2:
                    if not ga_df.empty:
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            display_ga = ga_df[['Airline/Flight', 'Count', 'Percentage']].head(20)
                            st.dataframe(display_ga, use_container_width=True, hide_index=True, height=400)
                        with col2:
                            top_ga = ga_df.head(15)
                            fig_ga = px.bar(
                                top_ga, 
                                x='Airline/Flight', 
                                y='Count',
                                title="Top 15 General Aviation Aircraft",
                                labels={'Airline/Flight': 'Tail Number', 'Count': 'Communications'},
                                color='Count',
                                color_continuous_scale='Greens'
                            )
                            fig_ga.update_layout(height=400, xaxis_tickangle=45, showlegend=False)
                            st.plotly_chart(fig_ga, use_container_width=True)
                    else:
                        st.info("No general aviation communications detected yet.")
                
                with airline_tab3:
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        display_all = known_df[['Airline/Flight', 'Count', 'Percentage', 'Type']].head(25)
                        st.dataframe(display_all, use_container_width=True, hide_index=True, height=400)
                    with col2:
                        # Pie chart showing distribution
                        type_counts = known_df.groupby('Type')['Count'].sum().reset_index()
                        fig_pie = px.pie(
                            type_counts,
                            values='Count',
                            names='Type',
                            title='Traffic Distribution',
                            color_discrete_map={'Commercial': '#1f77b4', 'General Aviation': '#2ca02c'}
                        )
                        fig_pie.update_layout(height=400)
                        st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No known airline data available yet. All entries are marked as 'Unknown'.")
        
        # Recent transcriptions table
        if transcription_df is not None and not transcription_df.empty:
            if auto_refresh:
                st.subheader("📋 Recent Transcriptions 🟢 Live")
            else:
                st.subheader("📋 Recent Transcriptions")
            
            # Sort by timestamp and get the most recent 5
            sorted_df = transcription_df.sort_values('timestamp_utc', ascending=False)
            
            # Select columns to display
            columns_to_show = ['timestamp_utc', 'airline', 'category', 'raw_transcription']
            recent_df = sorted_df.head(5)[columns_to_show].copy()
            
            # Clean the transcription text to remove copyright notices
            recent_df['raw_transcription'] = recent_df['raw_transcription'].apply(clean_transcription_text)
            
            # Format timestamp to be more readable
            recent_df['timestamp_utc'] = recent_df['timestamp_utc'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Rename columns for display
            recent_df.columns = ['Timestamp', 'Airline/Flight', 'Category', 'Communication']
            
            # Style the dataframe
            st.dataframe(
                recent_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                    "Airline/Flight": st.column_config.TextColumn("Airline/Flight", width="medium"),
                    "Category": st.column_config.TextColumn("Category", width="medium"),
                    "Communication": st.column_config.TextColumn("Communication", width="large"),
                }
            )
            
            # Show total count
            st.caption(f"Showing latest 5 of {len(transcription_df):,} total transcriptions")
    
    with tab2:
        st.header("Daily Analytics")
        
        # Communication Time Range
        if communication_df is not None and not communication_df.empty and advanced_stats['time_range']:
            st.subheader("⏰ Communication Time Range")
            
            time_range = advanced_stats['time_range']
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "First Communication",
                    time_range['first_communication'].strftime('%Y-%m-%d'),
                    delta=time_range['first_communication'].strftime('%H:%M:%S')
                )
            
            with col2:
                st.metric(
                    "Last Communication",
                    time_range['last_communication'].strftime('%Y-%m-%d'),
                    delta=time_range['last_communication'].strftime('%H:%M:%S')
                )
            
            with col3:
                st.metric(
                    "Total Days",
                    f"{time_range['total_days']}",
                    delta=f"{time_range['total_hours']:.1f} hours"
                )
            
            with col4:
                st.metric(
                    "Duration",
                    str(time_range['total_duration']).split('.')[0],
                    delta="HH:MM:SS"
                )
            
            st.markdown("---")
        
        # Signal Level and Duration Statistics
        if communication_df is not None and not communication_df.empty:
            st.subheader("📡 Signal & Duration Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 Signal Level (dBFS) Statistics**")
                
                if advanced_stats['signal_level_stats']:
                    signal_stats = advanced_stats['signal_level_stats']
                    
                    signal_table = pd.DataFrame({
                        'Metric': ['Min', 'Median', 'Mean', 'Std Dev', 'Max'],
                        'Value (dBFS)': [
                            f"{signal_stats['min']:.2f}",
                            f"{signal_stats['median']:.2f}",
                            f"{signal_stats['mean']:.2f}",
                            f"{signal_stats['std']:.2f}",
                            f"{signal_stats['max']:.2f}"
                        ]
                    })
                    st.dataframe(signal_table, use_container_width=True, hide_index=True)
                    
                    # Quick metrics
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Avg Signal", f"{signal_stats['mean']:.2f} dBFS")
                    with col_b:
                        st.metric("Signal Range", f"{signal_stats['max'] - signal_stats['min']:.2f} dB")
                else:
                    st.info("No signal level data available.")
            
            with col2:
                st.markdown("**⏱️ Communication Duration (Inter-arrival Time)**")
                
                if advanced_stats['duration_stats']:
                    duration_stats = advanced_stats['duration_stats']
                    
                    duration_table = pd.DataFrame({
                        'Metric': ['Min', 'Median', 'Mean', 'Std Dev', 'Max'],
                        'Value (seconds)': [
                            f"{duration_stats['min']:.2f}",
                            f"{duration_stats['median']:.2f}",
                            f"{duration_stats['mean']:.2f}",
                            f"{duration_stats['std']:.2f}",
                            f"{duration_stats['max']:.2f}"
                        ]
                    })
                    st.dataframe(duration_table, use_container_width=True, hide_index=True)
                    
                    # Quick metrics
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Avg Interval", f"{duration_stats['mean']:.1f} sec")
                    with col_b:
                        st.metric("Median Interval", f"{duration_stats['median']:.1f} sec")
                else:
                    st.info("No duration data available.")
            
            st.markdown("---")
            
            # Hourly Communication Frequency (EST Timezone)
            st.subheader("🕐 Hourly Communication Frequency (EST Timezone)")
            
            if advanced_stats['hourly_pattern_est']:
                hourly_counts = advanced_stats['hourly_pattern_est']
                
                # Create DataFrame for plotting
                hourly_df = pd.DataFrame(list(hourly_counts.items()), columns=['Hour', 'Count'])
                hourly_df = hourly_df.sort_values('Hour')
                
                # Create bar chart
                fig_hourly_est = go.Figure(data=[
                    go.Bar(
                        x=hourly_df['Hour'],
                        y=hourly_df['Count'],
                        marker_color='#4a90e2',
                        text=hourly_df['Count'],
                        textposition='outside'
                    )
                ])
                
                fig_hourly_est.update_layout(
                    title="Histogram of Communication Frequency per Hour (EST)",
                    xaxis_title="Local Time (EST)",
                    yaxis_title="Number of Communications",
                    height=500,
                    showlegend=False,
                    xaxis=dict(
                        tickmode='array',
                        tickvals=[0, 5, 10, 15, 20],
                        ticktext=[f"{h:02d}:00" for h in [0, 5, 10, 15, 20]]
                    ),
                    yaxis=dict(
                        gridcolor='rgba(128, 128, 128, 0.3)'
                    )
                )
                
                st.plotly_chart(fig_hourly_est, use_container_width=True)
                
                # Additional hourly statistics
                col_a, col_b, col_c, col_d = st.columns(4)
                
                counts_list = list(hourly_counts.values())
                peak_hour = max(hourly_counts, key=hourly_counts.get)
                min_hour = min(hourly_counts, key=hourly_counts.get)
                
                with col_a:
                    st.metric("Peak Hour (EST)", f"{peak_hour:02d}:00", delta=f"{hourly_counts[peak_hour]} comms")
                with col_b:
                    st.metric("Quietest Hour (EST)", f"{min_hour:02d}:00", delta=f"{hourly_counts[min_hour]} comms")
                with col_c:
                    st.metric("Avg per Hour", f"{np.mean(counts_list):.1f}")
                with col_d:
                    st.metric("Total Hours Active", f"{len(hourly_counts)}")
            else:
                st.info("No hourly pattern data available.")
        else:
            st.info("No communication data available yet.")
    
    with tab3:
        # Simple test - just show the data directly
        if stats['categories']:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Category Distribution")
                
                # Pie chart
                categories_df = pd.DataFrame(list(stats['categories'].items()), 
                                           columns=['Category', 'Count'])
                
                fig_pie = px.pie(categories_df, values='Count', names='Category',
                               title="Communication Categories")
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.subheader("📈 Category Counts")
                
                # Bar chart
                fig_bar = px.bar(categories_df, x='Category', y='Count',
                               title="Communications by Category")
                fig_bar.update_layout(height=400)
                fig_bar.update_xaxes(tickangle=45)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Category details table
            st.subheader("📋 Category Details")
            category_details = []
            for category, count in stats['categories'].items():
                percentage = (count / stats['total_transcriptions']) * 100
                
                # Get daily counts for this category
                daily_counts = stats['daily_category_counts'].get(category, {})
                avg_per_day = count / len(stats['daily_transcriptions']) if stats['daily_transcriptions'] else 0
                
                # Calculate additional daily statistics
                if daily_counts:
                    daily_values = list(daily_counts.values())
                    min_daily = min(daily_values)
                    max_daily = max(daily_values)
                    avg_daily = sum(daily_values) / len(daily_values)
                else:
                    min_daily = max_daily = avg_daily = 0
                
                category_details.append({
                    'Category': category,
                    'Total Count': count,
                    'Percentage': f"{percentage:.1f}%",
                    'Avg per Day': f"{avg_per_day:.1f}",
                    'Min Daily': min_daily,
                    'Max Daily': max_daily,
                    'Avg Daily': f"{avg_daily:.1f}"
                })
            
            category_df = pd.DataFrame(category_details)
            st.dataframe(category_df, use_container_width=True, hide_index=True)
            
            # Daily breakdown by category
            if stats['daily_category_counts']:
                st.subheader("📅 Daily Breakdown by Category")
                
                # Create a comprehensive daily breakdown table
                daily_breakdown_data = []
                all_dates = set()
                
                # Collect all unique dates
                for category_data in stats['daily_category_counts'].values():
                    all_dates.update(category_data.keys())
                
                all_dates = sorted(all_dates)
                
                # Create breakdown for each category
                for category, daily_counts in stats['daily_category_counts'].items():
                    row = {'Category': category}
                    total_for_category = 0
                    
                    for date in all_dates:
                        count = daily_counts.get(date, 0)
                        row[f"{date}"] = count
                        total_for_category += count
                    
                    row['Total'] = total_for_category
                    daily_breakdown_data.append(row)
                
                if daily_breakdown_data:
                    daily_breakdown_df = pd.DataFrame(daily_breakdown_data)
                    st.dataframe(daily_breakdown_df, use_container_width=True, hide_index=True)
        
        else:
            st.info("No category data available yet.")
    
    with tab4:
        st.header("Detailed Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📝 Transcription Statistics")
            
            if stats['duration_stats']:
                duration_table = pd.DataFrame({
                    'Metric': ['Mean Duration', 'Median Duration', 'Min Duration', 'Max Duration', 'Std Deviation'],
                    'Value (seconds)': [
                        f"{stats['duration_stats']['mean']:.1f}",
                        f"{stats['duration_stats']['median']:.1f}",
                        f"{stats['duration_stats']['min']:.1f}",
                        f"{stats['duration_stats']['max']:.1f}",
                        f"{stats['duration_stats']['std']:.1f}"
                    ]
                })
                st.dataframe(duration_table, use_container_width=True, hide_index=True)
            
            if stats['flight_stats']['total_flights'] > 0:
                st.subheader("✈️ Flight Statistics")
                flight_table = pd.DataFrame({
                    'Metric': ['Total Flights', 'Avg Communications per Flight', 'Max Communications per Flight'],
                    'Value': [
                        f"{stats['flight_stats']['total_flights']:,}",
                        f"{stats['flight_stats']['avg_comms_per_flight']:.1f}",
                        f"{stats['flight_stats']['max_comms_per_flight']:.0f}"
                    ]
                })
                st.dataframe(flight_table, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("🎙️ Audio Level Statistics")
            
            if 'audio_levels' in stats:
                audio_table = pd.DataFrame({
                    'Metric': ['Mean dBFS', 'Median dBFS', 'Min dBFS', 'Max dBFS'],
                    'Value': [
                        f"{stats['audio_levels']['mean']:.1f}",
                        f"{stats['audio_levels']['median']:.1f}",
                        f"{stats['audio_levels']['min']:.1f}",
                        f"{stats['audio_levels']['max']:.1f}"
                    ]
                })
                st.dataframe(audio_table, use_container_width=True, hide_index=True)
            else:
                st.info("No audio level data available.")
        
        # Raw data preview
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("📄 Raw Data Preview")
            st.dataframe(transcription_df.head(10), use_container_width=True)
    
    with tab5:
        st.header("Pattern Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if stats['hourly_pattern']:
                st.subheader("🕐 Hourly Activity Pattern")
                
                hourly_df = pd.DataFrame(list(stats['hourly_pattern'].items()), 
                                       columns=['Hour', 'Count'])
                hourly_df['Hour'] = hourly_df['Hour'].astype(int)
                hourly_df = hourly_df.sort_values('Hour')
                
                fig_hourly = px.bar(hourly_df, x='Hour', y='Count',
                                  title="Communications by Hour of Day")
                fig_hourly.update_layout(height=400)
                st.plotly_chart(fig_hourly, use_container_width=True)
        
        with col2:
            if transcription_df is not None and 'flight_number' in transcription_df.columns:
                st.subheader("✈️ Communications per Flight")
                
                flight_counts = transcription_df['flight_number'].value_counts().head(20)
                flight_df = pd.DataFrame({
                    'Flight': flight_counts.index,
                    'Communications': flight_counts.values
                })
                
                fig_flights = px.bar(flight_df, x='Flight', y='Communications',
                                   title="Top 20 Most Active Flights")
                fig_flights.update_layout(height=400)
                fig_flights.update_xaxes(tickangle=45)
                st.plotly_chart(fig_flights, use_container_width=True)
        
        # Communication intervals analysis
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("⏱️ Communication Timing Analysis")
            
            # Sort by timestamp and calculate intervals
            sorted_df = transcription_df.sort_values('timestamp_utc')
            intervals = []
            
            for i in range(1, len(sorted_df)):
                interval = (sorted_df.iloc[i]['timestamp_utc'] - 
                           sorted_df.iloc[i-1]['timestamp_utc']).total_seconds()
                intervals.append(interval)
            
            if intervals:
                intervals_df = pd.DataFrame({'interval_seconds': intervals})
                # Filter out very long intervals (likely day breaks)
                filtered_intervals = intervals_df[intervals_df['interval_seconds'] < 3600]
                
                if len(filtered_intervals) > 0:
                    interval_stats = {
                        'Metric': ['Average Interval', 'Median Interval', 'Min Interval', 'Max Interval'],
                        'Value (seconds)': [
                            f"{filtered_intervals['interval_seconds'].mean():.1f}",
                            f"{filtered_intervals['interval_seconds'].median():.1f}",
                            f"{filtered_intervals['interval_seconds'].min():.1f}",
                            f"{filtered_intervals['interval_seconds'].max():.1f}"
                        ]
                    }
                    
                    interval_stats_df = pd.DataFrame(interval_stats)
                    st.dataframe(interval_stats_df, use_container_width=True, hide_index=True)
                    
                    # Interval histogram
                    fig_intervals = px.histogram(filtered_intervals, x='interval_seconds',
                                               nbins=50, title="Distribution of Communication Intervals")
                    fig_intervals.update_layout(height=300)
                    st.plotly_chart(fig_intervals, use_container_width=True)
    
    # Footer
    st.markdown("---")
    if auto_refresh:
        st.markdown(
            """
            <div style='text-align: center; color: #666;'>
                🛫 ATC Voice Communications Dashboard | 🟢 Live Processing Active (Communications + Transcriptions)
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style='text-align: center; color: #666;'>
                🛫 ATC Voice Communications Dashboard | ⏸️ Manual Refresh Mode
            </div>
            """, 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
import requests
import io
import numpy as np
from pydub import AudioSegment
from datetime import datetime
import time
import re
import os
from pathlib import Path

# Configuration
STREAM_URL = "http://d.liveatc.net/zbw_ron4"
SEARCH_PAGE_URL = "https://www.liveatc.net/search/?icao=zbw"
CHUNK_SIZE = 1024
BUFFER_DURATION_SEC = 2.0
SILENCE_THRESHOLD_DB = -38 #For speech content

# Enhanced headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.liveatc.net/",
    "Origin": "https://www.liveatc.net",
    "Icy-MetaData": "1",
    "Connection": "keep-alive",
}

def setup_log_file():
    """Setup log file in ATC-Voice/src/data/logs directory."""
    # Set log directory - default to ATC-Voice/src/data/logs
    current_dir = Path.cwd()
    if "ATC-Voice" in str(current_dir):
        # We're somewhere in the ATC-Voice project
        atc_voice_root = current_dir
        while atc_voice_root.name != "ATC-Voice" and atc_voice_root.parent != atc_voice_root:
            atc_voice_root = atc_voice_root.parent
        log_dir = atc_voice_root / "src" / "data" / "logs"
    else:
        # Default fallback
        log_dir = Path("ATC-Voice/src/data/logs")
    
    # Create directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"atc_communications_{timestamp}.txt"
    log_filepath = log_dir / log_filename
    
    return log_filepath

def log_message(log_file, message, also_print=False):
    """Write message to log file and optionally print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    
    if also_print:
        print(f"[{timestamp}] {message}")

def is_communication_detected(audio_segment):
    """Detect communication if audio loudness exceeds threshold."""
    if not audio_segment:
        return False
    return audio_segment.dBFS > SILENCE_THRESHOLD_DB

def stream_and_detect_communications(stream_url):
    """Stream audio and detect communications - logging to file."""
    # Setup log file
    log_filepath = setup_log_file()
    
    # Initial log entries
    log_message(log_filepath, f"Starting to monitor LiveATC stream at {stream_url}...", True)
    log_message(log_filepath, f"Log file: {log_filepath.absolute()}", True)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Visit search page to set cookies
    try:
        session.get(SEARCH_PAGE_URL, timeout=10)
        log_message(log_filepath, "Established session with LiveATC site.")
    except Exception as e:
        log_message(log_filepath, f"Warning: Could not establish session: {e}")
    
    audio_buffer = bytearray()
    buffer_start_time = time.time()
    
    try:
        response = session.get(stream_url, stream=True, timeout=10, headers=session.headers)
        response.raise_for_status()
        
        log_message(log_filepath, "Successfully connected to stream. Monitoring for communications...", True)
        log_message(log_filepath, f"Silence threshold: {SILENCE_THRESHOLD_DB} dB", True)
        log_message(log_filepath, "Press Ctrl+C to stop monitoring", True)
        log_message(log_filepath, "")
        
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                audio_buffer.extend(chunk)
                
                # Check if buffer is ready for processing
                current_time = time.time()
                buffer_duration = current_time - buffer_start_time
                
                if buffer_duration >= BUFFER_DURATION_SEC:
                    try:
                        buffer_io = io.BytesIO(audio_buffer)
                        audio_segment = AudioSegment.from_file(buffer_io, format="mp3")
                        
                        if len(audio_segment) > 0:
                            # Detect and log communication
                            if is_communication_detected(audio_segment):
                                log_message(log_filepath, f"🎙️  Communication detected (dBFS: {audio_segment.dBFS:.1f})", True)
                        
                        # Reset buffer
                        audio_buffer = bytearray()
                        buffer_start_time = current_time
                        
                    except Exception as e:
                        log_message(log_filepath, f"Error processing audio buffer: {e}")
                        # Keep partial buffer to avoid losing data
                        if len(audio_buffer) > CHUNK_SIZE * 20:
                            audio_buffer = audio_buffer[-CHUNK_SIZE * 10:]
            
                # Prevent buffer overflow
                if len(audio_buffer) > 1024 * 1024:  # 1MB max
                    log_message(log_filepath, "Buffer overflow; resetting.")
                    audio_buffer = bytearray()
                    buffer_start_time = time.time()
                    
    except requests.exceptions.HTTPError as e:
        log_message(log_filepath, f"HTTP Error: {e}. LiveATC may require manual browser access or premium account.", True)
    except requests.exceptions.RequestException as e:
        log_message(log_filepath, f"Error connecting to stream: {e}", True)
    except KeyboardInterrupt:
        log_message(log_filepath, "🛑 Stopped monitoring LiveATC stream.", True)
    finally:
        log_message(log_filepath, "Monitoring ended.", True)
        log_message(log_filepath, f"Complete log saved to: {log_filepath.absolute()}", True)

if __name__ == "__main__":
    print("LiveATC Communication Detection Monitor")
    print("=" * 40)
    print("This script only detects and logs when communications occur.")
    print("No audio saving or transcription.\n")
    
    # Dependency check
    try:
        import pydub
        import numpy
        import requests
        print("✓ Core dependencies installed.\n")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        exit(1)
    
    stream_and_detect_communications(STREAM_URL)
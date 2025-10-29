import requests
import io
import numpy as np
from pydub import AudioSegment
from datetime import datetime
import time
from pathlib import Path

# Configuration
STREAM_URL = "http://d.liveatc.net/zbw_ron4"
SEARCH_PAGE_URL = "https://www.liveatc.net/search/?icao=zbw"
CHUNK_SIZE = 1024
BUFFER_DURATION_SEC = 2.0
SILENCE_THRESHOLD_DB = -38 # For speech content

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

def format_file_size(size_bytes):
    """Convert file size from bytes to human readable format (KB, MB, etc.)."""
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def setup_log_file():
    current_dir = Path.cwd()
    if "ATC-Voice" in str(current_dir):
        atc_voice_root = current_dir
        while atc_voice_root.name != "ATC-Voice" and atc_voice_root.parent != atc_voice_root:
            atc_voice_root = atc_voice_root.parent
        log_dir = atc_voice_root / "src" / "data" / "logs"
    else:
        log_dir = Path("ATC-Voice/src/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = "atc_communications.txt"
    log_filepath = log_dir / log_filename
    return log_filepath

def log_message(log_file, message, also_print=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    if also_print:
        print(f"[{timestamp}] {message}")

def check_existing_log(log_filepath):
    if log_filepath.exists():
        file_size = log_filepath.stat().st_size
        with open(log_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            line_count = len(lines)
            last_lines = lines[-3:] if len(lines) >= 3 else lines
        return True, file_size, line_count, last_lines
    return False, 0, 0, []

def is_communication_detected(audio_segment):
    if not audio_segment:
        return False
    return audio_segment.dBFS > SILENCE_THRESHOLD_DB

def stream_and_detect_communications(stream_url):
    log_filepath = setup_log_file()
    exists, file_size, line_count, last_lines = check_existing_log(log_filepath)
    
    if exists:
        formatted_size = format_file_size(file_size)
        print(f"📄 Found existing log file: {log_filepath.name}")
        print(f"   Size: {formatted_size} ({file_size:,} bytes) | Lines: {line_count:,}")
        print(f"   Last entries:")
        for line in last_lines:
            print(f"   {line.rstrip()}")
        print(f"\n✅ Continuing from where we left off...\n")
        log_message(log_filepath, "="*60)
        log_message(log_filepath, f"NEW SESSION STARTED - Continuing monitoring")
        log_message(log_filepath, "="*60)
    else:
        formatted_size = format_file_size(0)
        print(f"📝 Creating new log file: {log_filepath.name}")
        print(f"   Initial size: {formatted_size} | Lines: 0")

    log_message(log_filepath, f"Starting to monitor LiveATC stream at {stream_url}...", True)
    log_message(log_filepath, f"Log file: {log_filepath.absolute()}", True)

    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(SEARCH_PAGE_URL, timeout=10)
        log_message(log_filepath, "Established session with LiveATC site.")
    except Exception as e:
        log_message(log_filepath, f"Warning: Could not establish session: {e}")
    backoff = 5  # Starting backoff in seconds

    while True:
        audio_buffer = bytearray()
        buffer_start_time = time.time()
        try:
            response = session.get(stream_url, stream=True, timeout=(5, 15), headers=session.headers)
            response.raise_for_status()
            log_message(log_filepath, "Successfully connected to stream. Monitoring for communications...", True)
            log_message(log_filepath, f"Silence threshold: {SILENCE_THRESHOLD_DB} dB", True)
            log_message(log_filepath, "Press Ctrl+C to stop monitoring", True)
            log_message(log_filepath, "")
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    audio_buffer.extend(chunk)
                    current_time = time.time()
                    buffer_duration = current_time - buffer_start_time
                    if buffer_duration >= BUFFER_DURATION_SEC:
                        try:
                            buffer_io = io.BytesIO(audio_buffer)
                            audio_segment = AudioSegment.from_file(buffer_io, format="mp3")
                            if len(audio_segment) > 0:
                                if is_communication_detected(audio_segment):
                                    log_message(log_filepath, f"🎙️  Communication detected (dBFS: {audio_segment.dBFS:.1f})", True)
                            audio_buffer = bytearray()
                            buffer_start_time = current_time
                        except Exception as e:
                            log_message(log_filepath, f"Error processing audio buffer: {e}")
                            if len(audio_buffer) > CHUNK_SIZE * 20:
                                audio_buffer = audio_buffer[-CHUNK_SIZE * 10:]
                    if len(audio_buffer) > 1024 * 1024:  # 1MB max
                        log_message(log_filepath, "Buffer overflow; resetting.")
                        audio_buffer = bytearray()
                        buffer_start_time = time.time()
            # If finished cleanly, reset backoff
            backoff = 5
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            log_message(log_filepath, f"Error connecting to stream: {e}", True)
            log_message(log_filepath, f"Retrying in {backoff} seconds...", True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)  # Exponential backoff, max 60 seconds
        except KeyboardInterrupt:
            log_message(log_filepath, "🛑 Stopped monitoring LiveATC stream.", True)
            break
        except Exception as e:
            log_message(log_filepath, f"Unexpected error: {e}", True)
            log_message(log_filepath, f"Retrying in {backoff} seconds...", True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    log_message(log_filepath, "Monitoring ended.", True)
    log_message(log_filepath, f"Complete log saved to: {log_filepath.absolute()}", True)
    exists, file_size, line_count, _ = check_existing_log(log_filepath)
    if exists:
        formatted_size = format_file_size(file_size)
        print(f"\n📊 Final Statistics:")
        print(f"   Total log size: {formatted_size} ({file_size:,} bytes)")
        print(f"   Total log lines: {line_count:,}")

if __name__ == "__main__":
    print("LiveATC Communication Detection Monitor")
    print("=" * 40)
    print("This script only detects and logs when communications occur.")
    print("No audio saving or transcription.\n")
    try:
        import pydub
        import numpy
        import requests
        print("✓ Core dependencies installed.\n")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        exit(1)
    stream_and_detect_communications(STREAM_URL)
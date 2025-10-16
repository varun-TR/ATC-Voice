"""
ALL-IN-ONE: Unified ATC Recording & Transcription System
This single file contains everything - no separate imports needed!
"""

import os
import json
import time
import threading
import signal
import sys
import requests
import numpy as np
import librosa
from datetime import datetime, timezone
from faster_whisper import WhisperModel
from pathlib import Path
from pydub import AudioSegment
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import io
import subprocess


# ============================================================================
# SLIDING WINDOW AUDIO SPLITTER
# ============================================================================

class SlidingWindowAudioSplitter:
    def __init__(self, stream_url="http://d.liveatc.net/zbw_ron4", 
                 chunk_duration=30, overlap_duration=5, local_dir=None):
        self.stream_url = stream_url
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.slide_interval = chunk_duration - overlap_duration
        self.is_recording = False
        self.audio_buffer = deque()
        self.buffer_lock = threading.Lock()
        
        if local_dir:
            self.local_dir = Path(local_dir)
        else:
            self.local_dir = Path("src/data/raw")
        
        self.local_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Sliding window setup: {chunk_duration}s chunks, {overlap_duration}s overlap")
        print(f"📁 Local directory: {self.local_dir.absolute()}")

    def add_to_buffer(self, audio_data, timestamp):
        with self.buffer_lock:
            self.audio_buffer.append((audio_data, timestamp))
            max_buffer_items = int((self.chunk_duration + 10) * 10)
            while len(self.audio_buffer) > max_buffer_items:
                self.audio_buffer.popleft()

    def extract_window_audio(self, end_time):
        start_time = end_time - self.chunk_duration
        window_audio = b""
        
        with self.buffer_lock:
            for audio_data, timestamp in self.audio_buffer:
                if start_time <= timestamp <= end_time:
                    window_audio += audio_data
        
        return window_audio

    def save_chunk(self, chunk_data, chunk_number, window_start, window_end):
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            start_str = datetime.fromtimestamp(window_start).strftime("%H%M%S")
            end_str = datetime.fromtimestamp(window_end).strftime("%H%M%S")
            filename = f"atc_sliding_{chunk_number:03d}_{start_str}-{end_str}_{timestamp}.wav"
            filepath = self.local_dir / filename

            if len(chunk_data) < 1000:
                return None

            audio = AudioSegment.from_file(io.BytesIO(chunk_data), format="mp3")
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(str(filepath), format="wav")
            
            duration = len(audio) / 1000.0
            # Reduced verbosity - only show chunk number and duration
            print(f"📁 Chunk {chunk_number}: {duration:.1f}s")
            return filename

        except Exception as e:
            print(f"❌ Error saving chunk {chunk_number}: {e}")
            return None

    def download_stream(self):
        try:
            print(f"🌐 Connecting to stream: {self.stream_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'audio/*;q=0.9,*/*;q=0.5',
                'Connection': 'keep-alive',
            }

            response = requests.get(self.stream_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            
            print("✅ Connected! Buffering audio for sliding windows...")
            
            for chunk in response.iter_content(chunk_size=4096):
                if not self.is_recording:
                    break
                if chunk:
                    current_time = time.time()
                    self.add_to_buffer(chunk, current_time)

        except Exception as e:
            print(f"❌ Stream error: {e}")

    def sliding_window_processor(self):
        chunk_number = 1
        last_window_time = time.time()
        
        time.sleep(self.chunk_duration + 2)
        
        while self.is_recording:
            current_time = time.time()
            
            if current_time - last_window_time >= self.slide_interval:
                window_end = current_time
                window_start = window_end - self.chunk_duration
                
                window_audio = self.extract_window_audio(window_end)
                
                if window_audio:
                    self.save_chunk(window_audio, chunk_number, window_start, window_end)
                    chunk_number += 1
                
                last_window_time = current_time
            
            time.sleep(1)

    def start_recording(self, duration_minutes=None):
        print("🚀 Starting Sliding Window ATC Audio Splitter...")
        print("=" * 70)
        print(f"🌐 Stream URL: {self.stream_url}")
        print(f"📁 Local Directory: {self.local_dir.absolute()}")
        print(f"⏱️  Chunk duration: {self.chunk_duration} seconds")
        print(f"🔄 Overlap duration: {self.overlap_duration} seconds")
        print(f"⏭️  New chunk every: {self.slide_interval} seconds")
        if duration_minutes:
            print(f"⏰ Recording duration: {duration_minutes} minutes")
        print("=" * 70)

        self.is_recording = True
        
        download_thread = threading.Thread(target=self.download_stream, daemon=True)
        processor_thread = threading.Thread(target=self.sliding_window_processor, daemon=True)
        
        download_thread.start()
        processor_thread.start()

        try:
            if duration_minutes:
                print(f"⏰ Recording for {duration_minutes} minutes...")
                time.sleep(duration_minutes * 60)
                self.is_recording = False
                print("⏰ Recording time completed!")
            else:
                print("🎵 Recording with sliding windows... Press Ctrl+C to stop")
                while self.is_recording:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping recording...")
            self.is_recording = False

        download_thread.join(timeout=5)
        processor_thread.join(timeout=5)
        print("✅ Sliding window recording completed!")


# ============================================================================
# POSTPROCESSING TRIGGER
# ============================================================================

def trigger_postprocessing():
    """Trigger postprocessing of new transcriptions."""
    try:
        # Run postprocessing script silently
        postprocess_script = Path("src/nlp_analysis/postprocess.py")
        if postprocess_script.exists():
            result = subprocess.run([
                sys.executable, str(postprocess_script)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("🔄 Postprocessing completed")
            # Silent on warnings/errors to reduce noise
        # Silent on errors to reduce noise
            
    except subprocess.TimeoutExpired:
        print("⏰ Postprocessing timeout")
    except Exception as e:
        print(f"❌ Postprocessing error: {e}")


def start_dashboard():
    """Start the Streamlit dashboard in background."""
    try:
        print("🚀 Starting dashboard...")
        dashboard_script = Path("src/dashboard/app.py")
        if dashboard_script.exists():
            # Start dashboard in background
            subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", str(dashboard_script),
                "--server.port", "8501", "--server.headless", "true"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Dashboard started at http://localhost:8501")
        else:
            print("⚠️ Dashboard script not found")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")


# ============================================================================
# TRANSCRIPTION ENGINE
# ============================================================================

class TranscriptionEngine:
    def __init__(self, output_json, sample_rate=16_000):
        self.output_json = output_json
        self.sr = sample_rate
        self.model = None
        self.results = None
        self.processed_files = set()
        self.lock = threading.Lock()
        
    def initialize(self):
        print("🤖 Loading Whisper model (large-v3)...")
        # Use CPU instead of CUDA to avoid libcublas.so.12 errors
        self.model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        print("✅ Whisper model loaded!")
        self._load_results()
        
    def _load_results(self):
        if os.path.exists(self.output_json):
            try:
                with open(self.output_json, 'r', encoding='utf-8') as f:
                    self.results = json.load(f)
                    self.processed_files = {
                        item['audio_file_raw'] for item in self.results.get('items', [])
                    }
                print(f"📂 Loaded {len(self.processed_files)} existing transcriptions")
            except Exception as e:
                print(f"⚠️  Error loading results: {e}")
                self.results = None
        
        if self.results is None:
            self.results = {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "items": []
            }
    
    def _load_audio(self, path: str) -> np.ndarray:
        y, sr = librosa.load(path, sr=self.sr, mono=True)
        return y.astype(np.float32)
    
    def _transcribe_array(self, y: np.ndarray):
        segments, info = self.model.transcribe(y, language="en", beam_size=5)
        text = "".join(seg.text for seg in segments)
        return text.strip(), info.duration
    
    def _save_results(self):
        os.makedirs(os.path.dirname(self.output_json), exist_ok=True)
        with open(self.output_json, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
    
    def transcribe_file(self, filepath: str):
        with self.lock:
            if filepath in self.processed_files:
                print(f"⏭️  Already processed: {os.path.basename(filepath)}")
                return
            
            try:
                print(f"🎯 Transcribing: {os.path.basename(filepath)}")
                
                audio = self._load_audio(filepath)
                raw_transcript, raw_duration = self._transcribe_array(audio)
                
                chunk_number = len(self.results['items']) + 1
                item = {
                    "chunk_number": chunk_number,
                    "audio_file_raw": filepath,
                    "raw_duration_s": round(raw_duration, 2),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "raw_transcription": raw_transcript
                }
                
                self.results["items"].append(item)
                self.results["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
                self.processed_files.add(filepath)
                
                self._save_results()
                
                # Reduced verbosity - only show chunk number
                print(f"🎯 Transcribed chunk {chunk_number}")
                
                # Trigger postprocessing in background
                threading.Thread(target=trigger_postprocessing, daemon=True).start()
                
            except Exception as e:
                print(f"❌ Error transcribing {os.path.basename(filepath)}: {e}")


# ============================================================================
# FILE WATCHER
# ============================================================================

class AudioFileWatcher(FileSystemEventHandler):
    def __init__(self, transcription_engine, file_extension=".wav"):
        self.engine = transcription_engine
        self.file_extension = file_extension
        self.processing_queue = set()
        self.queue_lock = threading.Lock()
        
    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        if not filepath.lower().endswith(self.file_extension):
            return
        
        time.sleep(2)  # Wait for file to be fully written
        
        with self.queue_lock:
            if filepath in self.processing_queue:
                return
            self.processing_queue.add(filepath)
        
        try:
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                self.engine.transcribe_file(filepath)
        finally:
            with self.queue_lock:
                self.processing_queue.discard(filepath)


# ============================================================================
# SYNCHRONIZED SYSTEM
# ============================================================================

class SynchronizedATCSystem:
    def __init__(self, raw_dir="src/data/raw",
                 output_json="src/data/logs/transcripts/transcription_results.json"):
        self.raw_dir = Path(raw_dir)
        self.output_json = output_json
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        
        self.transcription_engine = TranscriptionEngine(output_json)
        self.file_watcher = AudioFileWatcher(self.transcription_engine)
        self.observer = None
        
    def initialize(self):
        print("=" * 70)
        print("🎙️  SYNCHRONIZED ATC RECORDING & TRANSCRIPTION SYSTEM")
        print("=" * 70)
        print(f"📁 Raw audio directory: {self.raw_dir.absolute()}")
        print(f"📝 Transcription output: {self.output_json}")
        print()
        
        self.transcription_engine.initialize()
        self._process_existing_files()
        
    def _process_existing_files(self):
        existing_files = sorted(self.raw_dir.glob("*.wav"))
        
        unprocessed = [
            str(f) for f in existing_files 
            if str(f) not in self.transcription_engine.processed_files
        ]
        
        if unprocessed:
            print(f"📋 Found {len(unprocessed)} unprocessed files. Transcribing...")
            for filepath in unprocessed:
                self.transcription_engine.transcribe_file(filepath)
        else:
            print("✅ All existing files already processed")
    
    def start_watching(self):
        print("\n👀 Starting file watcher...")
        print("   Waiting for new audio files to transcribe...")
        print("   Press Ctrl+C to stop")
        print("=" * 70)
        
        self.observer = Observer()
        self.observer.schedule(self.file_watcher, str(self.raw_dir), recursive=False)
        self.observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping file watcher...")
            self.observer.stop()
        
        self.observer.join()
        print("✅ System shutdown complete!")


# ============================================================================
# UNIFIED LAUNCHER
# ============================================================================

class UnifiedATCSystem:
    def __init__(self, stream_url="http://d.liveatc.net/zbw_ron4",
                 chunk_duration=30, overlap_duration=5,
                 raw_dir="src/data/raw",
                 output_json="src/data/logs/transcripts/transcription_results.json",
                 start_dashboard=False):
        
        self.stream_url = stream_url
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.raw_dir = Path(raw_dir)
        self.output_json = output_json
        self.start_dashboard = start_dashboard
        
        self.splitter = None
        self.transcriber = None
        self.running = False
        
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, sig, frame):
        print("\n\n🛑 Shutdown signal received...")
        self.stop()
        sys.exit(0)
    
    def initialize(self):
        print("=" * 80)
        print("🎙️  UNIFIED ATC RECORDING & TRANSCRIPTION SYSTEM")
        print("=" * 80)
        print(f"🌐 Stream: {self.stream_url}")
        print(f"⏱️  Chunk duration: {self.chunk_duration}s")
        print(f"🔄 Overlap: {self.overlap_duration}s")
        print(f"📁 Output directory: {self.raw_dir.absolute()}")
        print(f"📝 Transcription log: {self.output_json}")
        print("=" * 80)
        
        print("\n🔧 SYSTEM INITIALIZATION SEQUENCE")
        print("=" * 50)
        
        print("\n1️⃣  Initializing Audio Extraction System...")
        self.splitter = SlidingWindowAudioSplitter(
            stream_url=self.stream_url,
            chunk_duration=self.chunk_duration,
            overlap_duration=self.overlap_duration,
            local_dir=str(self.raw_dir)
        )
        print("✅ AUDIO EXTRACTION SYSTEM - READY")
        
        print("\n2️⃣  Initializing AI Modeling System...")
        self.transcriber = SynchronizedATCSystem(
            raw_dir=str(self.raw_dir),
            output_json=self.output_json
        )
        self.transcriber.initialize()
        print("✅ AI MODELING SYSTEM - READY")
        
        print("\n3️⃣  Initializing Transcription System...")
        print("✅ TRANSCRIPTION SYSTEM - READY")
        
        print("\n4️⃣  Initializing Postprocessing System...")
        print("✅ POSTPROCESSING SYSTEM - READY")
        
        # Start dashboard if requested
        if self.start_dashboard:
            print("\n5️⃣  Initializing UI Render System...")
            start_dashboard()
            print("✅ UI RENDER SYSTEM - READY")
        
        print("\n" + "=" * 50)
        print("🚀 ALL SYSTEMS INITIALIZED - READY FOR OPERATION")
        print("=" * 50)
        
    def start(self, duration_minutes=None):
        self.running = True
        
        print("\n" + "=" * 80)
        print("🚀 STARTING SYNCHRONIZED OPERATION")
        print("=" * 80)
        print("📡 Recording live ATC audio stream...")
        print("🤖 Transcribing audio files in real-time...")
        print("⌨️  Press Ctrl+C to stop")
        print("=" * 80)
        print()
        
        transcription_thread = threading.Thread(
            target=self.transcriber.start_watching,
            daemon=True
        )
        transcription_thread.start()
        
        time.sleep(2)
        
        try:
            self.splitter.start_recording(duration_minutes=duration_minutes)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self):
        if not self.running:
            return
            
        self.running = False
        print("\n🛑 Stopping systems...")
        
        if self.splitter:
            self.splitter.is_recording = False
            print("✅ Audio splitter stopped")
        
        if self.transcriber and self.transcriber.observer:
            self.transcriber.observer.stop()
            self.transcriber.observer.join(timeout=5)
            print("✅ Transcription watcher stopped")
        
        if self.transcriber:
            total = len(self.transcriber.transcription_engine.results['items'])
            print(f"\n📊 Final Statistics:")
            print(f"   Total audio chunks transcribed: {total}")
            print(f"   Results saved to: {self.output_json}")
        
        print("\n✅ System shutdown complete!")


# ============================================================================
# MAIN
# ============================================================================

def main():
    STREAM_URL = "http://d.liveatc.net/zbw_ron4"
    CHUNK_DURATION = 30
    OVERLAP_DURATION = 5
    DURATION_MINUTES = None  # None = run indefinitely
    START_DASHBOARD = True  # Set to True to start dashboard automatically
    
    print("\n" + "=" * 80)
    print("  🎙️  ATC LIVE RECORDING & TRANSCRIPTION SYSTEM")
    print("=" * 80)
    print(f"  Stream: NY Center Sector 9, Westminster High")
    print(f"  Mode: {CHUNK_DURATION}s chunks with {OVERLAP_DURATION}s overlap")
    print(f"  Duration: {'Continuous (Ctrl+C to stop)' if not DURATION_MINUTES else f'{DURATION_MINUTES} minutes'}")
    print(f"  Dashboard: {'Enabled' if START_DASHBOARD else 'Disabled'}")
    print("=" * 80)
    
    print("\n📋 HOW TO RUN THE SYSTEM:")
    print("=" * 50)
    print("1. Activate virtual environment: source venv/bin/activate")
    print("2. Run the system: python src/utils/all_in_one.py")
    print("3. Access dashboard: http://localhost:8501")
    print("4. Stop system: Press Ctrl+C")
    print("=" * 50)
    
    try:
        system = UnifiedATCSystem(
            stream_url=STREAM_URL,
            chunk_duration=CHUNK_DURATION,
            overlap_duration=OVERLAP_DURATION,
            start_dashboard=START_DASHBOARD
        )
        
        system.initialize()
        system.start(duration_minutes=DURATION_MINUTES)
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
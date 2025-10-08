import requests
import time
import threading
import queue
from datetime import datetime, timezone
from pydub import AudioSegment
import io
from pathlib import Path
from collections import deque

class SlidingWindowAudioSplitter:
    def __init__(self, stream_url="http://d.liveatc.net/zbw_ron4", 
                 chunk_duration=30, overlap_duration=5, local_dir=None):
        self.stream_url = stream_url
        self.chunk_duration = chunk_duration  # 30 seconds
        self.overlap_duration = overlap_duration  # 5 seconds
        self.slide_interval = chunk_duration - overlap_duration  # 25 seconds
        self.is_recording = False
        self.audio_buffer = deque()  # Rolling buffer for sliding window
        self.buffer_lock = threading.Lock()
        
        # Set local directory
        if local_dir:
            # Set local directory to ATC-Voice/src/data/raw
            self.local_dir = Path("ATC-Voice/src/data/raw")
        else:
            current_dir = Path.cwd()
            if "ATC-Voice" in str(current_dir):
                atc_voice_root = current_dir
                while atc_voice_root.name != "ATC-Voice" and atc_voice_root.parent != atc_voice_root:
                    atc_voice_root = atc_voice_root.parent
                self.local_dir = atc_voice_root / "src" / "data" / "raw"
            else:
                self.local_dir = Path("ATC-Voice/src/data/raw")
        
        self.local_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Sliding window setup: {chunk_duration}s chunks, {overlap_duration}s overlap")
        print(f"📁 Local directory: {self.local_dir.absolute()}")

    def add_to_buffer(self, audio_data, timestamp):
        """Add audio data to the sliding buffer."""
        with self.buffer_lock:
            self.audio_buffer.append((audio_data, timestamp))
            # Keep buffer size reasonable (enough for chunk_duration + some extra)
            max_buffer_items = int((self.chunk_duration + 10) * 10)  # ~10 items per second
            while len(self.audio_buffer) > max_buffer_items:
                self.audio_buffer.popleft()

    def extract_window_audio(self, end_time):
        """Extract audio for a specific time window."""
        start_time = end_time - self.chunk_duration
        window_audio = b""
        
        with self.buffer_lock:
            for audio_data, timestamp in self.audio_buffer:
                if start_time <= timestamp <= end_time:
                    window_audio += audio_data
        
        return window_audio

    def save_chunk(self, chunk_data, chunk_number, window_start, window_end):
        """Save audio chunk with sliding window metadata."""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            # Include window timing in filename
            start_str = datetime.fromtimestamp(window_start).strftime("%H%M%S")
            end_str = datetime.fromtimestamp(window_end).strftime("%H%M%S")
            filename = f"atc_sliding_{chunk_number:03d}_{start_str}-{end_str}_{timestamp}.wav"
            filepath = self.local_dir / filename

            if len(chunk_data) < 1000:  # Skip tiny chunks
                return None

            # Convert MP3 → WAV 16k mono PCM16
            audio = AudioSegment.from_file(io.BytesIO(chunk_data), format="mp3")
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            
            # Export to file
            audio.export(str(filepath), format="wav")
            
            duration = len(audio) / 1000.0  # seconds
            overlap_info = f"(5s overlap)" if chunk_number > 1 else "(no overlap)"
            print(f"💾 Saved: {filename} | Duration: {duration:.1f}s {overlap_info}")
            return filename

        except Exception as e:
            print(f"❌ Error saving chunk {chunk_number}: {e}")
            return None

    def download_stream(self):
        """Download live audio stream and buffer it."""
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
        """Process sliding windows every 25 seconds."""
        chunk_number = 1
        last_window_time = time.time()
        
        # Wait for initial buffer to fill
        time.sleep(self.chunk_duration + 2)
        
        while self.is_recording:
            current_time = time.time()
            
            if current_time - last_window_time >= self.slide_interval:
                window_end = current_time
                window_start = window_end - self.chunk_duration
                
                # Extract audio for this window
                window_audio = self.extract_window_audio(window_end)
                
                if window_audio:
                    self.save_chunk(window_audio, chunk_number, window_start, window_end)
                    chunk_number += 1
                
                last_window_time = current_time
            
            time.sleep(1)  # Check every second

    def start_recording(self, duration_minutes=None):
        """Start recording with sliding windows."""
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
        
        # Start background threads
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
        print(f"📁 Audio files saved to: {self.local_dir.absolute()}")


def main():
    print("🌐 ATC Sliding Window Audio Splitter")
    print("=" * 50)
    print("Stream: NY Center Sector 9, Westminster High")
    print("Window: 30-second chunks with 5-second overlap")
    print("Output: New file every 25 seconds")
    print("=" * 50)

    try:
        # 30-second chunks, 5-second overlap, new chunk every 25 seconds
        splitter = SlidingWindowAudioSplitter(
            chunk_duration=30,
            overlap_duration=5
        )
        splitter.start_recording()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")


if __name__ == "__main__":
    main()
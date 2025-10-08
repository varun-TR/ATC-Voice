import requests
import time
import threading
import queue
from datetime import datetime, timezone
from pydub import AudioSegment
import io
import os
from pathlib import Path

class LiveAudioStreamSplitter:
    def __init__(self, stream_url="http://d.liveatc.net/zbw_ron4", chunk_duration=30, local_dir=None):
        self.stream_url = stream_url
        self.chunk_duration = chunk_duration
        self.is_recording = False
        self.audio_queue = queue.Queue()

        # Set local directory - default to ATC-Voice/src/data/raw
        if local_dir:
            self.local_dir = Path(local_dir)
        else:
            # Try to find ATC-Voice directory structure
            current_dir = Path.cwd()
            if "ATC-Voice" in str(current_dir):
                # We're somewhere in the ATC-Voice project
                atc_voice_root = current_dir
                while atc_voice_root.name != "ATC-Voice" and atc_voice_root.parent != atc_voice_root:
                    atc_voice_root = atc_voice_root.parent
                self.local_dir = atc_voice_root / "src" / "data" / "raw"
            else:
                # Default fallback
                self.local_dir = Path("ATC-Voice/src/data/raw")

        # Create directory if it doesn't exist
        try:
            self.local_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Local directory ready: {self.local_dir.absolute()}")
        except Exception as e:
            raise RuntimeError(f"❌ Failed to create local directory '{self.local_dir}': {e}")

    def save_chunk(self, chunk_data, chunk_number):
        """Save audio chunk to local directory."""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"live_stream_chunk_{chunk_number:03d}_{timestamp}.wav"
            filepath = self.local_dir / filename

            # Convert incoming MP3 bytes → WAV 16k mono PCM16
            audio = AudioSegment.from_file(io.BytesIO(chunk_data), format="mp3")
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

            # Export directly to file
            audio.export(str(filepath), format="wav")
            
            print(f"💾 Saved locally: {filepath}")
            return filename

        except Exception as e:
            print(f"❌ Error saving chunk {chunk_number}: {e}")
            return None

    def download_stream(self):
        """Download live audio stream and put chunks in queue."""
        try:
            print(f"🌐 Connecting to stream: {self.stream_url}")

            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'audio/*;q=0.9,*/*;q=0.5',
                'Connection': 'keep-alive',
            }

            response = requests.get(self.stream_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            print("✅ Connected to stream successfully!")
            print("🎵 Recording audio...")

            chunk_data = b""
            chunk_start_time = time.time()

            for chunk in response.iter_content(chunk_size=8192):
                if not self.is_recording:
                    break

                if chunk:
                    chunk_data += chunk
                    current_time = time.time()

                    if current_time - chunk_start_time >= self.chunk_duration:
                        if len(chunk_data) > 1000:
                            self.audio_queue.put(chunk_data)
                        chunk_data = b""
                        chunk_start_time = current_time

        except requests.exceptions.RequestException as e:
            print(f"❌ Error connecting to stream: {e}")
        except Exception as e:
            print(f"❌ Error downloading stream: {e}")

    def save_chunks(self):
        """Save audio chunks from queue to local directory."""
        chunk_number = 1
        while self.is_recording or not self.audio_queue.empty():
            try:
                chunk_data = self.audio_queue.get(timeout=1)
                if chunk_data:
                    filename = self.save_chunk(chunk_data, chunk_number)
                    if filename:
                        size_mb = len(chunk_data) / (1024 * 1024)
                        print(f"📁 Saved: {filename} ({size_mb:.2f} MB)")
                        chunk_number += 1
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Error saving chunk {chunk_number}: {e}")

    def start_recording(self, duration_minutes=None):
        """Start recording the live stream."""
        print("🚀 Starting Live Audio Stream Splitter...")
        print("=" * 60)
        print(f"🌐 Stream URL: {self.stream_url}")
        print(f"📁 Local Directory: {self.local_dir.absolute()}")
        print(f"⏱️  Target chunk duration: ~{self.chunk_duration} seconds each")
        if duration_minutes:
            print(f"⏰ Recording duration: {duration_minutes} minutes")
        print("=" * 60)

        self.is_recording = True
        download_thread = threading.Thread(target=self.download_stream, daemon=True)
        save_thread = threading.Thread(target=self.save_chunks, daemon=True)
        download_thread.start()
        save_thread.start()

        try:
            if duration_minutes:
                print(f"⏰ Recording for {duration_minutes} minutes...")
                time.sleep(duration_minutes * 60)
                self.is_recording = False
                print("⏰ Recording time completed!")
            else:
                print("🎵 Recording... Press Ctrl+C to stop")
                while self.is_recording:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping recording...")
            self.is_recording = False

        download_thread.join(timeout=5)
        save_thread.join(timeout=5)
        print("✅ Recording completed!")
        print(f"📁 Audio files saved to: {self.local_dir.absolute()}")


def parse_playlist_file(playlist_path):
    """Parse PLS playlist file and extract stream URL."""
    try:
        with open(playlist_path, 'r') as f:
            content = f.read()
        for line in content.split('\n'):
            if line.startswith('File1='):
                return line.split('=', 1)[1].strip()
        return None
    except Exception as e:
        print(f"❌ Error parsing playlist file: {e}")
        return None


def main():
    print("🌐 ATC Audio Stream to Local Storage")
    print("=" * 50)
    print("Stream: http://d.liveatc.net/zbw_ron4 (NY Center Sector 9, Westminster High)")
    
    # Show where files will be stored
    current_dir = Path.cwd()
    if "ATC-Voice" in str(current_dir):
        atc_voice_root = current_dir
        while atc_voice_root.name != "ATC-Voice" and atc_voice_root.parent != atc_voice_root:
            atc_voice_root = atc_voice_root.parent
        local_dir = atc_voice_root / "src" / "data" / "raw"
    else:
        local_dir = Path("ATC-Voice/src/data/raw")
    
    print(f"Local Directory: {local_dir.absolute()}")
    print("Chunk Duration: 30 seconds")
    print("=" * 50)

    # Initialize splitter with default settings
    try:
        splitter = LiveAudioStreamSplitter()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Start recording continuously
    splitter.start_recording()


if __name__ == "__main__":
    main()
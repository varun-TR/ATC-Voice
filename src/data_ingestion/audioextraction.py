import requests
import time
import threading
import queue
import boto3
from datetime import datetime, timezone
from pydub import AudioSegment
import io
import os
from botocore.exceptions import ClientError, NoCredentialsError

class LiveAudioStreamSplitter:
    def __init__(self, stream_url="http://d.liveatc.net/zbw_ron4", chunk_duration=30, s3_bucket=None, s3_prefix=None):
        self.stream_url = stream_url
        self.chunk_duration = chunk_duration
        self.is_recording = False
        self.audio_queue = queue.Queue()

        # Bucket & prefix from args or env  
        self.s3_bucket = s3_bucket or os.environ.get('S3_BUCKET_NAME', 'raw.atc.audio')
        self.s3_prefix = (s3_prefix or 'uploads/rawaudio').lstrip('/')
        
        if not self.s3_prefix.endswith('/'):
            self.s3_prefix += '/'

        if not self.s3_bucket:
            raise ValueError("❌ S3 bucket name must be provided")

        # Initialize S3 client and validate access
        try:
            region = os.environ.get("AWS_DEFAULT_REGION")
            self.s3_client = boto3.client("s3", region_name=region) if region else boto3.client("s3")
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            print(f"✅ S3 bucket '{self.s3_bucket}' is accessible")
            # Optional: show actual bucket region to avoid surprises
            loc = self.s3_client.get_bucket_location(Bucket=self.s3_bucket)["LocationConstraint"] or "us-east-1"
            if region and region != loc:
                print(f"⚠️  Bucket region is '{loc}', AWS_DEFAULT_REGION is '{region}'. Prefer setting AWS_DEFAULT_REGION='{loc}'.")
        except NoCredentialsError:
            raise RuntimeError("❌ AWS credentials not found. Set ~/.aws/credentials or environment variables.")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("403", "AccessDenied"):
                raise RuntimeError(f"❌ Access denied to bucket '{self.s3_bucket}'.")
            if code in ("404", "NoSuchBucket"):
                raise RuntimeError(f"❌ Bucket '{self.s3_bucket}' does not exist.")
            if code in ("301", "PermanentRedirect"):
                raise RuntimeError(f"❌ Wrong region for bucket '{self.s3_bucket}'. Set AWS_DEFAULT_REGION to the bucket's region.")
            raise
        except Exception as e:
            raise RuntimeError(f"❌ S3 setup error: {e}") from e

    def _build_key(self, filename: str) -> str:
        """Build S3 key for the file."""
        return f"{self.s3_prefix}{filename}"

    def save_chunk(self, chunk_data, chunk_number):
        """Upload audio chunk directly to S3 under the configured prefix."""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"live_stream_chunk_{chunk_number:03d}_{timestamp}.wav"
            key = self._build_key(filename)

            # Convert incoming MP3 bytes → WAV 16k mono PCM16
            audio = AudioSegment.from_file(io.BytesIO(chunk_data), format="mp3")
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=wav_io.read(),
                ContentType="audio/wav",
                Metadata={
                    "source": "liveatc",
                    "stream_url": self.stream_url,
                    "chunk_number": str(chunk_number),
                    "chunk_duration_sec": str(self.chunk_duration),
                    "ingest_ts_utc": timestamp,
                },
            )
            print(f"☁️ Uploaded to S3: s3://{self.s3_bucket}/{key}")
            return filename

        except Exception as e:
            if "Unable to locate credentials" in str(e):
                print(f"❌ AWS credentials not configured. Would upload: s3://{self.s3_bucket}/{self._build_key('...')}")
            else:
                print(f"❌ Error uploading chunk {chunk_number}: {e}")
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
        """Save audio chunks from queue to S3."""
        chunk_number = 1
        while self.is_recording or not self.audio_queue.empty():
            try:
                chunk_data = self.audio_queue.get(timeout=1)
                if chunk_data:
                    filename = self.save_chunk(chunk_data, chunk_number)
                    if filename:
                        size_mb = len(chunk_data) / (1024 * 1024)
                        print(f"💾 Uploaded: {filename} ({size_mb:.2f} MB)")
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
        print(f"☁️ S3 Bucket: {self.s3_bucket}")
        print(f"📁 S3 Prefix: {self.s3_prefix}")
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
    print("🌐 ATC Audio Stream to S3 Uploader")
    print("=" * 50)
    print("Stream: http://d.liveatc.net/zbw_ron4 (NY Center Sector 9, Westminster High)")

    # Show bucket/prefix from env (or defaults)
    s3_bucket = os.environ.get('S3_BUCKET_NAME', 'raw.atc.audio')
    s3_prefix = 'uploads/rawaudio'  # Fixed to correct path
    print(f"S3 Bucket: {s3_bucket}")
    print(f"S3 Prefix: {s3_prefix}")
    print("Chunk Duration: 30 seconds")
    print("=" * 50)

    # Initialize splitter with default settings
    try:
        splitter = LiveAudioStreamSplitter(s3_bucket=s3_bucket, s3_prefix=s3_prefix)
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("\n💡 To fix this:")
        print("1. Ensure ~/.aws/credentials and ~/.aws/config are set (with session token).")
        print("2. Or export env vars: AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY/SESSION_TOKEN/AWS_DEFAULT_REGION")
        return

    # Start recording continuously
    splitter.start_recording()


if __name__ == "__main__":
    main()
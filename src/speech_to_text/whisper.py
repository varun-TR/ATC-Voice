import os
import json
import numpy as np
import librosa
import noisereduce as nr
from datetime import datetime, timezone
from faster_whisper import WhisperModel


RAW_DIR = "ATC-Voice/src/data/raw"
OUTPUT_JSON = "ATC-Voice/src/data/logs/transcripts/transcription_results.json"
SR = 16_000

def iso_utc():
    return datetime.now(timezone.utc).isoformat()

def load_audio(path: str) -> np.ndarray:
    y, sr = librosa.load(path, sr=SR, mono=True)
    return y.astype(np.float32)

def denoise_stationary(y: np.ndarray) -> np.ndarray:
    n = int(0.5 * SR)
    noise_clip = y[:n] if y.size > n else y
    return nr.reduce_noise(y=y, y_noise=noise_clip, sr=SR, stationary=True)

def denoise_spectral(y: np.ndarray) -> np.ndarray:
    return nr.reduce_noise(y=y, sr=SR)

def transcribe_array(model: WhisperModel, y: np.ndarray):
    segments, info = model.transcribe(y, language="en", beam_size=5)
    text = "".join(seg.text for seg in segments)
    return text.strip(), info.duration

def save_json_results(results, output_path):
    """Save results to JSON file"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

# Initialize whisper model
print("Loading Whisper model...")
model = WhisperModel("large-v3", device="cuda", compute_type="float16")

# Initialize results structure
results = {
    "created_utc": iso_utc(),
    "items": []
}

# Process files
chunk_number = 1
wav_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(".wav")]
wav_files.sort()  # Sort for consistent ordering

print(f"Processing {len(wav_files)} audio files...")

for fname in wav_files:
    fpath = os.path.join(RAW_DIR, fname)
    
    print(f"Processing {chunk_number}/{len(wav_files)}: {fname}")
    
    # Load audio
    audio = load_audio(fpath)
    
    # Get transcriptions
    raw_transcript, raw_duration = transcribe_array(model, audio)
    
    y_stat = denoise_stationary(audio)
    stat_transcript, stat_duration = transcribe_array(model, y_stat)
    
    y_spec = denoise_spectral(audio)
    spec_transcript, spec_duration = transcribe_array(model, y_spec)
    
    # Create item for JSON in your specified format
    item = {
        "chunk_number": chunk_number,
        "audio_file_raw": fpath,
        "raw_duration_s": round(raw_duration, 2),
        "timestamp_utc": iso_utc(),
        "raw_transcription": raw_transcript,
        "stationary_transcription": stat_transcript,
        "spectral_transcription": spec_transcript
    }
    
    # Add item to results
    results["items"].append(item)
    
    # Save JSON file immediately after processing each file
    save_json_results(results, OUTPUT_JSON)
    
    print(f"✅ File {chunk_number} processed and saved to JSON")
    chunk_number += 1

print(f"\n🎯 All transcription complete! Final results saved to: {OUTPUT_JSON}")
print(f"Total files processed: {len(results['items'])}")
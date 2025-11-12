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
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from dataclasses import dataclass
import math
import statistics

# Set page config
st.set_page_config(
    page_title="CATSR Live Communications Dashboard",
    page_icon="🛫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
BASE_DIR = Path(".")
TRANSCRIPTIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "transcripts" / "categorized_transcription_results.json"
COMMUNICATIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "atc_communications.txt"
AIRLINE_CALLSIGN_FILE = BASE_DIR / "config" / "airline_callsign (2).json"
PHONETIC_ALPHABET_FILE = BASE_DIR / "config" / "phonetic_alphabet (1).json"
AIRLINE_NNUMBERS_FILE = BASE_DIR / "config" / "airline_nnumbers.json"

# ----------------------------- Airline Detection Logic ----------------------------- #
@st.cache_resource
def load_airline_configs():
    """Load airline callsign, phonetic alphabet, and N-numbers configs."""
    try:
        with open(AIRLINE_CALLSIGN_FILE, 'r', encoding='utf-8') as f:
            callsigns = json.load(f)

        with open(PHONETIC_ALPHABET_FILE, 'r', encoding='utf-8') as f:
            phonetic_dict = json.load(f)

        with open(AIRLINE_NNUMBERS_FILE, 'r', encoding='utf-8') as f:
            nnumber_lookup = json.load(f)

        return callsigns, phonetic_dict, nnumber_lookup
    except Exception as e:
        st.error(f"Error loading airline configs: {e}")
        return {}, {}, {}

def words_to_digits(word: str) -> str:
    """Convert spelled numbers to digits."""
    mapping = {
        'zero': '0', 'oh': '0', 'o': '0',
        'one': '1', 'won': '1',
        'two': '2', 'too': '2',
        'three': '3', 'tree': '3',
        'four': '4', 'fore': '4',
        'five': '5', 'fife': '5',
        'six': '6',
        'seven': '7',
        'eight': '8', 'ate': '8',
        'nine': '9', 'niner': '9'
    }
    return mapping.get(word, word)

def combine_number_words(tokens: List[str]) -> List[str]:
    """Combine tens and ones words (e.g., 'twenty one' -> '21')."""
    tens_map = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
    }
    result = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in tens_map and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if nxt in ["one","two","three","four","five","six","seven","eight","nine"]:
                num = tens_map[tok] + int(words_to_digits(nxt))
                result.append(str(num))
                i += 2
                continue
        result.append(tok)
        i += 1
    return result

def normalize_numbers(tokens: List[str]) -> List[str]:
    """Convert spelled numbers in list of tokens to digits."""
    return [words_to_digits(tok) for tok in tokens]

def decode_phonetic_sequence(text: str, phonetic_dict: Dict[str, str]) -> str:
    """Decode phonetic alphabet sequences into letters."""
    tokens = re.split(r"[\s\-]+", text.lower().strip())
    tokens = combine_number_words(tokens)
    tokens = normalize_numbers(tokens)
    decoded = []
    for tok in tokens:
        if tok in phonetic_dict:
            decoded.append(phonetic_dict[tok].upper())
        elif tok.isdigit():
            decoded.append(tok)
        elif len(tok) == 1 and tok.isalpha():
            decoded.append(tok.upper())
    return " ".join(decoded)

def preprocess_transcript(text: str) -> str:
    """Normalize transcript for airline matching."""
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9\s\-]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()

def is_valid_ga_tail(tail: str) -> bool:
    """Validate FAA general aviation tail number format."""
    if not tail or not tail.startswith("N"):
        return False
    tail = tail.upper()
    if len(tail) > 6:
        return False
    m = re.match(r"^N([1-9]\d{0,4})([A-HJ-NP-Z]{0,2})$", tail)
    if not m:
        return False
    n_digits = m.group(1)
    letters = m.group(2)
    if 1 <= int(n_digits) <= 99 and not letters:
        return False
    return True

def preprocess_transcript_airline(text: str) -> str:
    """Normalize transcript for airline matching."""
    if not text or text.strip() == "":
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_callsign(text: str,
                    callsigns: Dict[str, list],
                    phonetic_dict: Dict[str, str],
                    nnumber_lookup: Dict[str, str]) -> str:
    """Detect airline or general aviation callsign using comprehensive logic."""
    if not text:
        return "Unknown"

    t = preprocess_transcript(text)
    tokens = re.split(r"[\s\-]+", t)
    tokens = combine_number_words(tokens)
    tokens = normalize_numbers(tokens)

    # --- 1️⃣ Airline / military alias detection ---
    decoded_flat = decode_phonetic_sequence(t, phonetic_dict)
    decoded_flat_clean = re.sub(r"[^A-Z0-9]", "", decoded_flat)
    for airline, aliases in callsigns.items():
        aliases = [aliases] if isinstance(aliases, str) else aliases
        for alias in aliases:
            alias_low = alias.lower()
            alias_up = alias.upper()
            if alias_low == "india" and not re.search(r"\bair\s+india\b", t):
                continue
            if alias_low == "delta":
                if re.search(r"\b(lufthansa|american|united|jetblue|british|air\s+canada|air\s+france)\b", t):
                    continue
                if re.search(
                        r"\bdelta (alpha|bravo|charlie|delta|echo|foxtrot|golf|hotel|india|juliet|kilo|lima|mike|november|oscar|papa|quebec|romeo|sierra|tango|uniform|victor|whiskey|xray|yankee|zulu)\b",
                        t):
                    continue
                if re.search(
                        r"\bdelta (\d+|one|two|three|four|five|six|seven|eight|nine|zero|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
                        t
                ):
                    return airline

                continue
            if alias_up in decoded_flat_clean or re.search(rf"\b{re.escape(alias_low)}\b", t):
                return airline

    # --- November-based N-number detection (FAA format) ---
    if "november" in t:
        after = re.split(r"\bnovember\b", t, maxsplit=1)[-1].strip()
        parts = re.split(r"[\s\-]+", after)
        tail_raw = "".join(
            [phonetic_dict.get(p, p).upper() if p in phonetic_dict else p for p in parts[:6]]
        )
        tail = "N" + re.sub(r"[^A-Z0-9]", "", tail_raw)

        # must contain both digits & letters
        if re.search(r"\d", tail) and re.search(r"[A-Z]", tail) and is_valid_ga_tail(tail):
            owner_name = nnumber_lookup.get(tail, "")
            if owner_name:
                return f"General Aviation ({tail})"
            else:
                return "Unknown"

    # --- No "November" → detect mixed digit-letter patterns---
    tail_tokens: List[str] = []
    for i, tok in enumerate(tokens + ["STOP"]):
        tok_low = tok.lower()
        if tok.isdigit() or tok_low in phonetic_dict:
            tail_tokens.append(tok)
        else:
            if tail_tokens:
                tail_raw = "".join(
                    [phonetic_dict.get(x.lower(), x).upper() if x.lower() in phonetic_dict else x.upper()
                     for x in tail_tokens]
                )
                tail_raw = re.sub(r"[^A-Z0-9]", "", tail_raw)
                # require at least one digit and one letter
                if not (re.search(r"\d", tail_raw) and re.search(r"[A-Z]", tail_raw)):
                    tail_tokens = []
                    continue
                tail = "N" + tail_raw
                if is_valid_ga_tail(tail):
                    owner_name = nnumber_lookup.get(tail, "")
                    if owner_name:
                        return f"General Aviation ({tail})"
                    else:
                        return "Unknown"
            tail_tokens = []

    return "Unknown"

@st.cache_data(ttl=3)  # Cache for 3 seconds - ensures fresh data with 10s auto-refresh
def load_transcription_data(_refresh_key: int = 0) -> Optional[pd.DataFrame]:
    """Load and parse transcription data from JSON file. _refresh_key forces cache invalidation."""
    try:
        if not TRANSCRIPTIONS_FILE.exists():
            return None
        
        with open(TRANSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Handle corrupted JSON with extra data or partial last object
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            msg = str(e)
            # Attempt salvage for both 'Extra data' and 'Expecting value' by truncating items to last complete object
            try:
                items_key_idx = content.find('"items"')
                arr_start = content.find('[', items_key_idx)
                if items_key_idx != -1 and arr_start != -1:
                    cutoff = max(0, e.pos - 1)
                    up_to_err = content[:cutoff]
                    last_obj_end = up_to_err.rfind('}')
                    if last_obj_end != -1 and last_obj_end > arr_start:
                        # Build a minimally valid JSON up to the last complete item
                        prefix = content[:arr_start + 1]
                        items_part = content[arr_start + 1:last_obj_end + 1]
                        # Ensure we don't end with a trailing comma
                        items_part = items_part.rstrip()
                        if items_part.endswith(','):
                            items_part = items_part[:-1]
                        repaired = prefix + items_part + "\n  ]\n}"
                        data = json.loads(repaired)
                        st.warning("⚠️ Detected corrupted JSON near the end. Loaded data up to the last complete item.")
                    else:
                        raise e
                else:
                    raise e
            except Exception:
                # If salvage fails and the error was specifically 'Extra data', try previous path
                if "Extra data" in msg:
                    valid_json = content[:e.pos].rstrip()
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
        
        # Use existing airline data from JSON, only re-detect for "Unknown" entries
        if 'airline' not in df.columns:
            df['airline'] = 'Unknown'
        
        # Only re-detect airlines for entries marked as "Unknown"
        callsigns, phonetic_dict, nnumber_lookup = load_airline_configs()
        if callsigns:  # Only if configs loaded successfully
            unknown_mask = df['airline'] == 'Unknown'
            if unknown_mask.any():
                # Create a function that returns both airline and registration name
                def detect_with_registration(text):
                    airline = detect_callsign(text, callsigns, phonetic_dict, nnumber_lookup)
                    registration_name = None
                    if airline.startswith("General Aviation"):
                        match = re.search(r"\((N[0-9A-Z]+)\)", airline)
                        if match:
                            tail = match.group(1)
                            owner = nnumber_lookup.get(tail)
                            if owner:
                                if isinstance(owner, list):
                                    owner = " ".join(owner)
                                registration_name = str(owner)
                    return airline, registration_name

                # Apply detection and get both airline and registration name
                results = df.loc[unknown_mask, 'raw_transcription'].apply(detect_with_registration)
                df.loc[unknown_mask, 'airline'] = results.apply(lambda x: x[0])
                df['registration_name'] = None  # Initialize column
                df.loc[unknown_mask, 'registration_name'] = results.apply(lambda x: x[1])
        
        return df
    
    except Exception as e:
        st.error(f"Error loading transcription data: {e}")
        return None

@st.cache_data(ttl=3)  # Cache for 3 seconds - ensures fresh data with 10s auto-refresh
def load_communication_logs(_refresh_key: int = 0) -> Optional[pd.DataFrame]:
    """Load and parse communication detection logs. _refresh_key forces cache invalidation."""
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

# ====== ATC-Pilot Pairing Logic (adapted from pair_timeinterval_atc.py) ======

# Configurable dictionaries (ICAO/FAA-informed)
NATO = {
    "alpha":"A","bravo":"B","charlie":"C","delta":"D","echo":"E","foxtrot":"F","golf":"G",
    "hotel":"H","india":"I","juliett":"J","kilo":"K","lima":"L","mike":"M","november":"N",
    "oscar":"O","papa":"P","quebec":"Q","romeo":"R","sierra":"S","tango":"T","uniform":"U",
    "victor":"V","whiskey":"W","x-ray":"X","xray":"X","yankee":"Y","zulu":"Z"
}
NUM_WORDS = {
    "zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5",
    "six":"6","seven":"7","eight":"8","nine":"9"
}
UNIT_HINTS = [
    "tower","ground","approach","departure","center","centre","control","delivery",
]
ATC_VERBS = [
    "cleared","maintain","climb","descend","contact","turn","reduce","increase",
    "hold","expect","squawk","proceed","vector","resume","cross","expedite",
]
PILOT_VERBS = [
    "request","ready","with you","checking in","leaving","climbing","descending",
    "for departure","for taxi","landing","takeoff","on final","line up","wilco","roger",
]
ACK_ONLY = [
    "roger","wilco","thank you","thanks","copied","affirm","negative","good day",
    "morning","afternoon","evening"
]
JUNK_PAT = re.compile(r"^[\W_\.]+$")

def normalize_text(s: str) -> str:
    s = s.strip()
    # common ellipses / filler purge
    s = re.sub(r"[•·…]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def lower_letters_digits(s: str) -> str:
    return re.sub(r"[^a-z0-9\s\-]", " ", s.lower())

def expand_nato_numbers(t: str) -> str:
    """Map NATO + number words so 'delta one two three' -> 'D 1 2 3'"""
    out = []
    for w in t.split():
        if w in NATO: out.append(NATO[w])
        elif w in NUM_WORDS: out.append(NUM_WORDS[w])
        else: out.append(w)
    return " ".join(out)

def looks_like_callsign(t: str) -> Optional[str]:
    """
    Heuristic callsign detector (post NATO expansion):
      - patterns like 'DAL 123', 'AAL 45', 'UAE 7', 'N123AB', etc.
    """
    t = t.upper()
    # N-prefix GA (US), or 2–3 letters + 1–4 digits
    m = re.search(r"\b([A-Z]{2,3}\s?\d{1,4}[A-Z]{0,2}|N\d{2,5}[A-Z]{0,2})\b", t)
    return m.group(1).replace(" ", "") if m else None

def contains_any(t: str, vocab: List[str]) -> bool:
    t = " " + t.lower() + " "
    return any(f" {w} " in t for w in vocab)

def label_role(text_clean: str, callsign_present: bool) -> str:
    """
    Score-based role guess:
      - If unit hint or strong ATC verbs appear ⇒ ATC
      - If request/readback phrasing dominates ⇒ PILOT
      - If ambiguous, use callsign presence and default to PILOT for short readbacks.
    """
    atc_score = 0
    pilot_score = 0

    if contains_any(text_clean, UNIT_HINTS): atc_score += 2
    if contains_any(text_clean, ATC_VERBS): atc_score += 2
    if contains_any(text_clean, PILOT_VERBS): pilot_score += 2

    length = len(text_clean.split())
    if length <= 3 and contains_any(text_clean, ["with you","checking in","departing"]):
        pilot_score += 1
    if length <= 3 and contains_any(text_clean, ["contact","maintain","climb","descend"]):
        atc_score += 1

    # short acknowledgments go to PILOT by default
    if length <= 2 and contains_any(text_clean, ACK_ONLY):
        pilot_score += 2

    # callsign presence helps both; slight weight toward PILOT for readbacks
    if callsign_present:
        pilot_score += 1
        atc_score += 1

    if atc_score > pilot_score: return "ATC"
    if pilot_score > atc_score: return "PILOT"
    # tie-breakers
    if length <= 3: return "PILOT"
    return "ATC"

def is_junk(text: str) -> bool:
    t = text.strip()
    if not t: return True
    if JUNK_PAT.match(t): return True
    # very short acknowledgments only?
    low = t.lower()
    if any(low == w for w in ["roger","wilco","thanks","thank you",".","..","..."]):
        return True
    # mostly dots
    if set(low) <= set(". "): return True
    # only 1 word & not alnum
    tokens = re.findall(r"[A-Za-z0-9]+", t)
    return len(tokens) == 0

@dataclass
class Utt:
    idx: int
    ts: float       # epoch seconds
    text: str
    text_clean: str
    callsign: Optional[str]
    role: str       # "ATC" or "PILOT"

def preprocess_for_pairing(transcription_df: pd.DataFrame) -> List[Utt]:
    """Convert transcription DataFrame to Utt objects for pairing analysis."""
    out: List[Utt] = []

    for i, row in transcription_df.iterrows():
        raw = normalize_text(row.get("raw_transcription", ""))
        if is_junk(raw):
            continue

        norm = lower_letters_digits(raw)
        norm = expand_nato_numbers(norm)
        cs = looks_like_callsign(norm)
        role = label_role(norm, cs is not None)

        try:
            # Convert timestamp to epoch seconds
            ts = row['timestamp_utc'].timestamp()
        except Exception:
            continue

        out.append(Utt(idx=i, ts=ts, text=raw, text_clean=norm, callsign=cs, role=role))

    # temporal sort
    out.sort(key=lambda u: u.ts)
    return out

def pair_communications(utts: List[Utt], base_window: float = 12.0, grace: float = 2.0) -> Tuple[List[Dict], List[Utt]]:
    """Pair ATC <-> Pilot communications and measure response times."""
    pairs = []
    used = set()
    n = len(utts)

    for i, u in enumerate(utts):
        if i in used:
            continue
        # Skip pure acknowledgments for pairing
        if any(f" {w} " in (" " + u.text_clean + " ") for w in ACK_ONLY):
            continue

        best = None
        best_score = -1.0
        for j in range(i+1, n):
            v = utts[j]
            if j in used:
                continue
            dt = v.ts - u.ts
            if dt < 0:
                continue
            if dt > base_window + grace:
                break

            score = 0.0
            # callsign exact match = strong score
            if u.callsign and v.callsign and u.callsign == v.callsign:
                score += 3.0
            # role alternation is desired
            if u.role != v.role:
                score += 2.0
            # control/request keyword cross
            if contains_any(u.text_clean, ATC_VERBS) and contains_any(v.text_clean, PILOT_VERBS):
                score += 1.0
            if contains_any(u.text_clean, PILOT_VERBS) and contains_any(v.text_clean, ATC_VERBS):
                score += 1.0
            # tighter time gets a bonus
            score += max(0.0, (base_window - dt) / base_window)

            # Only consider if within base_window OR strong callsign+alternation in grace
            # Require minimum score of 2.0 (at least role alternation)
            if (dt <= base_window or (dt <= base_window + grace and score >= 4.0)) and score >= 2.0:
                if score > best_score:
                    best_score, best = score, (j, v, dt)

        if best is not None:
            j, v, dt = best
            used.add(i); used.add(j)
            d = "ATC_to_PILOT" if u.role == "ATC" and v.role == "PILOT" else "PILOT_to_ATC"
            pairs.append({
                "i": u.idx, "j": v.idx,
                "t1_utc": u.ts, "t2_utc": v.ts,
                "delta_sec": round(dt, 3),
                "dir": d,
                "callsign": u.callsign if u.callsign else (v.callsign or ""),
                "u_role": u.role, "v_role": v.role,
                "u_text": u.text, "v_text": v.text,
            })

    orphans = [utts[k] for k in range(n) if k not in used]
    return pairs, orphans

def calculate_response_time_stats(pairs: List[Dict]) -> Dict[str, Any]:
    """Calculate response time statistics for ATC-to-Pilot and Pilot-to-ATC communications."""
    atc_to_pilot = [p["delta_sec"] for p in pairs if p["dir"] == "ATC_to_PILOT"]
    pilot_to_atc = [p["delta_sec"] for p in pairs if p["dir"] == "PILOT_to_ATC"]

    def compute_stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"count": 0, "avg_sec_trimmed": 0, "p50_sec": 0, "p90_sec": 0}
        vals = sorted(values)
        # 10% trimmed mean to avoid long gaps bias
        k = int(0.1 * len(vals))
        trimmed = vals[k: len(vals)-k] if len(vals) > 2*k+1 else vals
        avg = sum(trimmed)/len(trimmed)
        def pct(p):
            if not vals: return 0.0
            i = max(0, min(len(vals)-1, int(round((p/100.0)*(len(vals)-1)))))
            return vals[i]
        return {
            "count": len(vals),
            "avg_sec_trimmed": round(avg, 5),
            "p50_sec": round(pct(50), 3),
            "p90_sec": round(pct(90), 3),
        }

    stats = {
        "ATC_to_PILOT": compute_stats(atc_to_pilot),
        "PILOT_to_ATC": compute_stats(pilot_to_atc),
        "total_pairs": len(pairs)
    }

    # Overall combined stats
    all_times = atc_to_pilot + pilot_to_atc
    if all_times:
        combined_stats = compute_stats(all_times)
        stats["combined"] = combined_stats

    return stats

@st.cache_data(ttl=60)
def calculate_atc_pilot_response_times(transcription_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Calculate ATC-to-Pilot and Pilot-to-ATC response time statistics."""
    if transcription_df is None or transcription_df.empty:
        return {
            "ATC_to_PILOT": {"count": 0, "avg_sec_trimmed": 0, "p50_sec": 0, "p90_sec": 0},
            "PILOT_to_ATC": {"count": 0, "avg_sec_trimmed": 0, "p50_sec": 0, "p90_sec": 0},
            "total_pairs": 0
        }

    # Preprocess transcriptions
    utts = preprocess_for_pairing(transcription_df)

    # Pair communications with tighter window for aviation (pilots respond within 1-2 seconds)
    pairs, orphans = pair_communications(utts, base_window=3.0, grace=1.0)

    # Calculate statistics
    stats = calculate_response_time_stats(pairs)

    return stats

@st.cache_data(ttl=3)  # Cache for 3 seconds - ensures fresh data with 10s auto-refresh
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
    
    # Hourly Pattern (assumed local/EST from parsed timestamps)
    if 'hour' in communication_df.columns:
        hourly_counts = communication_df.groupby('hour').size()
        stats['hourly_pattern_est'] = {int(k): int(v) for k, v in hourly_counts.items()}
    
    return stats

@st.cache_data(ttl=3)  # Cache for 3 seconds - ensures fresh data with 10s auto-refresh
def extract_airport_status(transcription_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Extract airport/runway status information from transcriptions."""
    status = {
        'runway_conditions': {'count': 0, 'recent': []},
        'lighting_status': {'count': 0, 'recent': []},
        'airport_operations': {'count': 0, 'recent': []},
        'closure_alerts': {'count': 0, 'recent': []},
        'total_status_updates': 0
    }

    if transcription_df is None or transcription_df.empty:
        return status

    # Keywords for different status types
    runway_patterns = [
        r'runway.*wet', r'runway.*dry', r'runway.*snow', r'runway.*ice',
        r'runway.*closed', r'runway.*open', r'friction', r'braking action',
        r'runway.*condition', r'runway.*surface'
    ]

    lighting_patterns = [
        r'light.*on', r'light.*off', r'lighting.*control', r'runway.*light',
        r'taxiway.*light', r'approach.*light', r'landing.*light'
    ]

    operations_patterns = [
        r'airport.*closed', r'airport.*open', r'ground.*stop', r'ground.*delay',
        r'all.*stop', r'emergency', r'ground.*control', r'tower.*closed'
    ]

    closure_patterns = [
        r'closed.*runway', r'closed.*taxiway', r'notam', r'closure',
        r'maintenance', r'construction', r'temporarily.*closed'
    ]

    # Process each transcription
    for idx, row in transcription_df.iterrows():
        text = row['raw_transcription'].lower()
        timestamp = row['timestamp_utc']

        # Check runway conditions
        if any(re.search(pattern, text) for pattern in runway_patterns):
            status['runway_conditions']['count'] += 1
            if len(status['runway_conditions']['recent']) < 3:
                status['runway_conditions']['recent'].append({
                    'time': timestamp.strftime('%H:%M'),
                    'message': row['raw_transcription'][:60] + '...' if len(row['raw_transcription']) > 60 else row['raw_transcription']
                })

        # Check lighting status
        if any(re.search(pattern, text) for pattern in lighting_patterns):
            status['lighting_status']['count'] += 1
            if len(status['lighting_status']['recent']) < 3:
                status['lighting_status']['recent'].append({
                    'time': timestamp.strftime('%H:%M'),
                    'message': row['raw_transcription'][:60] + '...' if len(row['raw_transcription']) > 60 else row['raw_transcription']
                })

        # Check airport operations
        if any(re.search(pattern, text) for pattern in operations_patterns):
            status['airport_operations']['count'] += 1
            if len(status['airport_operations']['recent']) < 3:
                status['airport_operations']['recent'].append({
                    'time': timestamp.strftime('%H:%M'),
                    'message': row['raw_transcription'][:60] + '...' if len(row['raw_transcription']) > 60 else row['raw_transcription']
                })

        # Check closure alerts
        if any(re.search(pattern, text) for pattern in closure_patterns):
            status['closure_alerts']['count'] += 1
            if len(status['closure_alerts']['recent']) < 3:
                status['closure_alerts']['recent'].append({
                    'time': timestamp.strftime('%H:%M'),
                    'message': row['raw_transcription'][:60] + '...' if len(row['raw_transcription']) > 60 else row['raw_transcription']
                })

    status['total_status_updates'] = (
        status['runway_conditions']['count'] +
        status['lighting_status']['count'] +
        status['airport_operations']['count'] +
        status['closure_alerts']['count']
    )

    return status

@st.cache_data(ttl=3)  # Cache for 3 seconds - ensures fresh data with 10s auto-refresh
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
        'flight_number_stats': {},  # Flight number communication counts
        'duplicate_stats': {
            'duplicate_count': 0,
            'duplicate_percentage': 0.0
        },
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
            'total_flights': len(flight_counts),
            'avg_comms_per_flight': flight_counts.mean() if len(flight_counts) > 0 else 0,
            'max_comms_per_flight': flight_counts.max() if len(flight_counts) > 0 else 0
        }
        
        # Flight number statistics (for Pattern Analysis tab)
        stats['flight_number_stats'] = flight_counts.to_dict()
        
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

        # Duplicate statistics
        if 'duplicate_flag' in transcription_df.columns:
            duplicate_count = transcription_df['duplicate_flag'].sum()
            total_count = len(transcription_df)
            duplicate_percentage = (duplicate_count / total_count * 100) if total_count > 0 else 0.0
            stats['duplicate_stats'] = {
                'duplicate_count': int(duplicate_count),
                'duplicate_percentage': duplicate_percentage
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

@st.cache_data(ttl=10)
def _build_minute_counts(communication_df: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    """Aggregate communication detections into per-minute counts (timestamps already in local time from log)."""
    if communication_df is None or communication_df.empty or 'timestamp' not in communication_df.columns:
        return None
    df = communication_df[['timestamp']].copy()
    df['ts'] = pd.to_datetime(df['timestamp'])
    df.set_index('ts', inplace=True)
    # Count events per minute; fill missing minutes with 0 within observed range
    per_min = df['timestamp'].resample('T').count()
    if per_min.empty:
        return None
    # Ensure continuous index
    full_idx = pd.date_range(start=per_min.index.min(), end=per_min.index.max(), freq='T')
    per_min = per_min.reindex(full_idx, fill_value=0)
    per_min.name = 'count'
    return per_min


def _normal_pi(mu: float, z: float, phi: float = 1.0) -> Tuple[float, float]:
    """Normal-approx prediction interval for a (possibly overdispersed) Poisson mean mu.
    phi>=1 inflates variance: Var = phi * mu
    """
    sigma = np.sqrt(max(mu * max(phi, 1.0), 1e-9))
    low = max(0.0, mu - z * sigma)
    high = mu + z * sigma
    return low, high


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _poisson_tail_normal_approx(k: int, mu: float, phi: float = 1.0) -> float:
    """Approximate P(X >= k) for X~Poisson-like(mean=mu, var=phi*mu) using normal with continuity correction."""
    if mu <= 0:
        return 0.0 if k > 0 else 1.0
    sigma = np.sqrt(max(mu * max(phi, 1.0), 1e-9))
    z = (k - 0.5 - mu) / sigma
    return float(1.0 - _phi(z))


@st.cache_data(ttl=10)
def forecast_minute_counts(minute_series: pd.Series, horizon_minutes: int = 60, window_minutes: int = 180, bias_correction: bool = False) -> Optional[pd.DataFrame]:
    """Simple overdispersed Poisson-like forecast using recent mean/variance.
    Returns per-minute forecast with widened prediction intervals. Optionally applies short-term bias correction.
    """
    if minute_series is None or len(minute_series) < 5:
        return None
    minute_series = minute_series.sort_index()
    end_time = minute_series.index.max()
    start_window = end_time - pd.Timedelta(minutes=window_minutes - 1)
    window = minute_series.loc[minute_series.index >= start_window]
    if window.empty:
        window = minute_series.tail(window_minutes)
    lam = float(window.mean()) if len(window) > 0 else float(minute_series.mean())
    lam = max(lam, 1e-6)
    # Overdispersion factor phi = Var / Mean (clamped >=1)
    var_hat = float(window.var(ddof=1)) if len(window) > 1 else lam
    phi = max(var_hat / max(lam, 1e-6), 1.0)

    # Optional multiplicative bias correction using recent short window
    bias_factor = 1.0
    if bias_correction:
        short = window.tail(max(5, min(15, window_minutes // 6)))
        if len(short) > 0:
            short_mean = float(short.mean())
            if lam > 0:
                bias_factor = short_mean / lam
                # clamp mild correction to avoid instability
                bias_factor = float(np.clip(bias_factor, 0.8, 1.25))

    future_idx = pd.date_range(start=end_time + pd.Timedelta(minutes=1), periods=horizon_minutes, freq='T')

    rows = []
    for ts in future_idx:
        mu = lam * bias_factor
        low50, high50 = _normal_pi(mu, z=0.674, phi=phi)
        low80, high80 = _normal_pi(mu, z=1.282, phi=phi)
        low95, high95 = _normal_pi(mu, z=1.960, phi=phi)
        rows.append({
            'timestamp': ts,
            'mean': mu,
            'pi50_low': low50, 'pi50_high': high50,
            'pi80_low': low80, 'pi80_high': high80,
            'pi95_low': low95, 'pi95_high': high95
        })

    fcst = pd.DataFrame(rows).set_index('timestamp')
    fcst.attrs['lambda'] = lam
    fcst.attrs['phi'] = phi
    fcst.attrs['bias_factor'] = bias_factor
    fcst.attrs['window_minutes'] = window_minutes
    return fcst


@st.cache_data(ttl=10)
def backtest_minute_forecast(minute_series: pd.Series, window_minutes: int = 180, horizon: int = 1, test_minutes: int = 720) -> Optional[Dict[str, Any]]:
    """Rolling-origin backtest for 1-step-ahead minute forecasts over the recent test window,
    using dispersion-widened intervals and proper naive baseline for MASE (lag-1)."""
    if minute_series is None or len(minute_series) < window_minutes + horizon + 5:
        return None
    s = minute_series.sort_index()
    end_time = s.index.max()
    start_bt = end_time - pd.Timedelta(minutes=test_minutes)
    s_bt = s.loc[s.index >= start_bt]
    if len(s_bt) < window_minutes + horizon + 5:
        s_bt = s.tail(window_minutes + horizon + 25)

    preds = []
    trues = []
    naive_preds = []
    cover80 = []
    cover95 = []

    times = list(s_bt.index)
    for i in range(window_minutes, len(times) - horizon):
        t = times[i]
        hist_start = t - pd.Timedelta(minutes=window_minutes - 1)
        hist = s.loc[(s.index >= hist_start) & (s.index <= t)]
        lam = float(hist.mean()) if len(hist) > 0 else float(s.mean())
        lam = max(lam, 1e-6)
        # dispersion from history
        var_hat = float(hist.var(ddof=1)) if len(hist) > 1 else lam
        phi = max(var_hat / max(lam, 1e-6), 1.0)
        # predict next minute (mean)
        mu = lam
        true_val = float(s.loc[times[i + horizon]])
        preds.append(mu)
        trues.append(true_val)
        # Naive baseline = last observed value at time t
        naive_preds.append(float(s.loc[t]))
        # Coverage indicators using widened intervals
        low80, high80 = _normal_pi(mu, 1.282, phi)
        low95, high95 = _normal_pi(mu, 1.960, phi)
        cover80.append(1 if (true_val >= low80 and true_val <= high80) else 0)
        cover95.append(1 if (true_val >= low95 and true_val <= high95) else 0)

    if not preds:
        return None

    preds_arr = np.array(preds)
    trues_arr = np.array(trues)
    naive_arr = np.array(naive_preds)

    mae = float(np.mean(np.abs(trues_arr - preds_arr)))
    naive_mae = float(np.mean(np.abs(trues_arr - naive_arr))) if len(naive_arr) == len(trues_arr) else None
    mase = float(mae / (naive_mae + 1e-9)) if naive_mae is not None else None

    results = {
        'mae': mae,
        'mase_vs_naive': mase,
        'n': int(len(preds)),
        'pi80_coverage': float(np.mean(cover80)) if cover80 else None,
        'pi95_coverage': float(np.mean(cover95)) if cover95 else None,
        'preds': preds_arr.tolist(),
        'trues': trues_arr.tolist(),
        'naive': naive_arr.tolist()
    }
    return results

def main():
    st.title("🛫 CATSR Live Communications Dashboard")
    st.markdown("---")
    
    # Simple manual refresh approach - no auto-refresh issues!
    st.sidebar.info("🔄 Data Refresh")
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data Now", key="refresh_button", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    
    st.sidebar.caption("💡 Click button to update with latest data")
    st.sidebar.caption("⌨️ Or use browser refresh (F5)")
    
    # Sidebar with data status
    st.sidebar.header("📊 Data Status")
    
    # Data source indicators
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if TRANSCRIPTIONS_FILE.exists():
            st.success(f"📝 Transcriptions: {TRANSCRIPTIONS_FILE.name}")
            st.caption("✅ Data available")
        else:
            st.error("📝 No transcription data")
    
    with col2:
        if COMMUNICATIONS_FILE.exists():
            st.success(f"🎙️ Communications: {COMMUNICATIONS_FILE.name}")
            st.caption("✅ Data available")
        else:
            st.error("🎙️ No communication logs")
    
    # Load data with refresh key to force cache invalidation
    refresh_key = st.session_state.get('refresh_counter', 0)
    with st.spinner("Loading ATC data..."):
        transcription_df = load_transcription_data(_refresh_key=refresh_key)
        communication_df = load_communication_logs(_refresh_key=refresh_key)
    
    # Calculate statistics
    stats = calculate_stats(transcription_df, communication_df)
    advanced_stats = calculate_advanced_comm_stats(communication_df)
    airport_status = extract_airport_status(transcription_df)
    response_times = calculate_atc_pilot_response_times(transcription_df)
    
    # Show last update time prominently
    last_update_str = stats['last_update'].strftime('%H:%M:%S')
    st.sidebar.markdown(f"**Last Update:** {last_update_str}")

    # ZNY Sector Chart
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗺️ ZNY Sector 09")
    st.sidebar.caption("New York ARTCC High Altitude Charts")

    # Load and display the ZNY chart
    chart_path = "src/utils/map.jpeg"
    try:
        st.sidebar.image(chart_path, caption="Sector 09 Monitoring", use_container_width=True)
        st.sidebar.markdown("**📍 Current Sector:** 09")
    except Exception as e:
        st.sidebar.error(f"Unable to load sector chart: {e}")
        st.sidebar.info("ZNY High Altitude Sector Chart - Sector 09")

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
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Transcriptions Processed", 
                f"{stats['total_transcriptions']:,}",
                delta=f"Total recorded"
            )
        
        with col2:
            st.metric(
                "Communication Detections",
                f"{stats['total_communications']:,}",
                delta=f"Total detected"
            )
        
        with col3:
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
            unknown_df = airline_df[airline_df['Airline/Flight'] == 'Unknown'].copy()
            unknown_entries_count = len(unknown_df)  # Count of unknown entries
            unknown_comms_sum = unknown_df['Count'].sum() if not unknown_df.empty else 0  # Total communications
            
            if not known_df.empty:
                known_df = known_df.sort_values('Count', ascending=False)
                
                # Add percentage column
                total_known = known_df['Count'].sum()
                known_df['Percentage'] = (known_df['Count'] / total_known * 100).round(1)
                known_df['Percentage'] = known_df['Percentage'].astype(str) + '%'
                
                # Split into commercial and GA
                commercial_df = known_df[known_df['Type'] == 'Commercial'].copy()
                ga_df = known_df[known_df['Type'] == 'General Aviation'].copy()

                # Add registration name column for GA aircraft
                def get_registration_name(airline_str):
                    if 'General Aviation' in airline_str:
                        match = re.search(r'\((N[0-9A-Z]+)\)', airline_str)
                        if match:
                            n_number = match.group(1)
                            callsigns, phonetic_dict, nnumber_lookup = load_airline_configs()
                            if nnumber_lookup and n_number in nnumber_lookup:
                                owner = nnumber_lookup[n_number]
                                if isinstance(owner, list):
                                    owner = " ".join(owner)
                                return str(owner)
                    return None

                ga_df['registration_name'] = ga_df['Airline/Flight'].apply(get_registration_name)
                
                # Summary metrics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("🛫 Detected Commercial Airlines", len(commercial_df), 
                             delta=f"{commercial_df['Count'].sum()} comms")
                with col2:
                    st.metric("🛩️ Detected General Aviation", len(ga_df), 
                             delta=f"{ga_df['Count'].sum()} comms")
                
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
                            display_commercial = commercial_df[['Airline/Flight', 'Count', 'Percentage']]
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
                            display_ga = ga_df[['Airline/Flight', 'registration_name', 'Count']].rename(
                                columns={'Airline/Flight': 'Tail Number', 'registration_name': 'Registration Name'}
                            )
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
                                color_continuous_scale='Greens',
                                hover_data=['registration_name']
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
                st.markdown("**⏱️ ATC-Pilot Response Times**")

                if response_times and response_times.get('total_pairs', 0) > 0:
                    st.caption("💡 Using 3-second pairing window for aviation communications (pilots typically respond within 1-2 seconds)")

                    # Communication duration table showing ATC-to-Pilot and Pilot-to-ATC only
                    response_table = pd.DataFrame({
                        'Direction': ['ATC → Pilot', 'Pilot → ATC'],
                        'Pairs': [
                            response_times['ATC_to_PILOT']['count'],
                            response_times['PILOT_to_ATC']['count']
                        ],
                        'Avg Response (sec)': [
                            f"{response_times['ATC_to_PILOT']['avg_sec_trimmed']:.1f}",
                            f"{response_times['PILOT_to_ATC']['avg_sec_trimmed']:.1f}"
                        ],
                        'Median (sec)': [
                            f"{response_times['ATC_to_PILOT']['p50_sec']:.1f}",
                            f"{response_times['PILOT_to_ATC']['p50_sec']:.1f}"
                        ],
                        '90th %ile (sec)': [
                            f"{response_times['ATC_to_PILOT']['p90_sec']:.1f}",
                            f"{response_times['PILOT_to_ATC']['p90_sec']:.1f}"
                        ]
                    })
                    st.dataframe(response_table, use_container_width=True, hide_index=True)
                else:
                    st.info("No response time data available yet. Need more transcription pairs to analyze.")
            
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

                def _fmt_hour_ampm(h: int) -> str:
                    h = int(h) % 24
                    suffix = "AM" if h < 12 else "PM"
                    h12 = 12 if (h % 12) == 0 else (h % 12)
                    return f"{h12}:00 {suffix}"
                
                with col_a:
                    st.metric("Peak Hour (EST)", _fmt_hour_ampm(peak_hour), delta=f"{hourly_counts[peak_hour]} comms")
                with col_b:
                    st.metric("Quietest Hour (EST)", _fmt_hour_ampm(min_hour), delta=f"{hourly_counts[min_hour]} comms")
                with col_c:
                    st.metric("Avg per Hour", f"{np.mean(counts_list):.1f}")
                with col_d:
                    st.metric("Total Hours Active", f"{len(hourly_counts)}")

                if int(peak_hour) < 7:
                    st.info("Peak hour appears early in the day. If unexpected, verify the timestamp timezone of communication logs.")
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

            # Duplicate transmissions statistics
            if stats['duplicate_stats']['duplicate_count'] > 0:
                st.subheader("🔄 Duplicate Transmissions")
                duplicate_table = pd.DataFrame({
                    'Metric': ['Repeated or Redundant Transmissions', 'Percentage of Total'],
                    'Value': [
                        f"{stats['duplicate_stats']['duplicate_count']:,}",
                        f"{stats['duplicate_stats']['duplicate_percentage']:.1f}%"
                    ]
                })
                st.dataframe(duplicate_table, use_container_width=True, hide_index=True)

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

            # Airport/Runway Status section
            st.subheader("🏢 Airport Operations Status")
            st.caption("Real-time monitoring of airport conditions from ATC communications")

            if airport_status['total_status_updates'] > 0:
                # Status summary table
                status_summary = pd.DataFrame({
                    'Airport Status Category': ['Runway Surface Conditions', 'Runway & Taxiway Lighting', 'Airport Operations', 'Runway/Taxiway Closures', 'Total Status Messages'],
                    'Messages Detected': [
                        airport_status['runway_conditions']['count'],
                        airport_status['lighting_status']['count'],
                        airport_status['airport_operations']['count'],
                        airport_status['closure_alerts']['count'],
                        airport_status['total_status_updates']
                    ]
                })
                st.dataframe(status_summary, use_container_width=True, hide_index=True)
            else:
                st.info("No airport status updates detected in recent communications.")
        
    
    with tab5:
        st.header("Pattern Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Removed '✈️ Unique Flights Detected' per request
            pass
        
        with col2:
            # Removed 'Communications per Flight' per request
            pass
        
        # Removed '⏱️ Communication Timing Analysis' per request
        
        # ---------------- Traffic Volume Forecasting ----------------
        st.subheader("📈 ATC Traffic Forecast: Predicting Communication Volume")
        st.caption("Real-time prediction of how many radio communication detections per minute to expect in the near future")
        
        minute_series = _build_minute_counts(communication_df)
        if minute_series is None:
            st.info("No communication detections available to forecast yet.")
        else:
            col_cfg, col_risk = st.columns([2, 1])
            with col_cfg:
                st.markdown("**⚙️ Forecast Settings:**")
                horizon = st.slider(
                    "How far ahead to predict (minutes)", 
                    min_value=15, max_value=180, value=60, step=5,
                    help="Choose how many minutes into the future you want to see predictions for"
                )
                window = st.slider(
                    "Historical data window (minutes)", 
                    min_value=30, max_value=720, value=180, step=30,
                    help="How much past data to use for making predictions. Larger windows = more stable but less responsive to recent changes"
                )
                bias_on = st.checkbox(
                    "Recent trend adjustment", 
                    value=False,
                    help="Give more weight to very recent data patterns (last 5-15 minutes)"
                )
            with col_risk:
                st.markdown("**🚨 Alert Threshold:**")
                threshold = st.number_input(
                    "Communication detections per minute", 
                    min_value=0, value=10, step=1,
                    help="Set threshold to calculate risk of exceeding this communication rate"
                )
            
            # Forecast
            fcst = forecast_minute_counts(minute_series, horizon_minutes=horizon, window_minutes=window, bias_correction=bias_on)
            if fcst is None or fcst.empty:
                st.info("Insufficient history to produce a forecast.")
            else:
                lam = float(fcst.attrs.get('lambda', float(minute_series.mean())))
                phi = float(fcst.attrs.get('phi', 1.0))
                bias_factor = float(fcst.attrs.get('bias_factor', 1.0))
                # History (last 24h)
                hist = minute_series.tail(24 * 60)
                hist_df = pd.DataFrame({'timestamp': hist.index, 'count': hist.values})
                
                # Build forecast dataframe for plotting
                plot_df = pd.DataFrame({
                    'timestamp': fcst.index,
                    'mean': fcst['mean'],
                    'pi80_low': fcst['pi80_low'], 'pi80_high': fcst['pi80_high'],
                    'pi95_low': fcst['pi95_low'], 'pi95_high': fcst['pi95_high']
                })
                
                # Timestamps are already in EST (local time from log file), no conversion needed
                hist_df['timestamp_est'] = pd.to_datetime(hist_df['timestamp'])
                plot_df['timestamp_est'] = pd.to_datetime(plot_df['timestamp'])
                
                # Plot history + forecast with ribbons
                fig = go.Figure()
                
                # Historical actual data
                fig.add_trace(go.Scatter(
                    x=hist_df['timestamp_est'], 
                    y=hist_df['count'],
                    mode='lines', 
                    name='📊 Actual History (Past Communications)',
                    line=dict(color='#444', width=2),
                    hovertemplate='<b>Historical Data</b><br>' +
                                  'Time: %{x|%Y-%m-%d %H:%M}<br>' +
                                  'Communications: %{y:.0f} per minute<br>' +
                                  '<extra></extra>'
                ))
                
                # 95% confidence interval (outer band)
                fig.add_trace(go.Scatter(
                    x=plot_df['timestamp_est'], 
                    y=plot_df['pi95_high'],
                    mode='lines', 
                    line=dict(color='rgba(31,119,180,0)'), 
                    showlegend=False,
                    hoverinfo='skip'
                ))
                fig.add_trace(go.Scatter(
                    x=plot_df['timestamp_est'], 
                    y=plot_df['pi95_low'],
                    fill='tonexty', 
                    mode='lines', 
                    name='95% Confidence (Very Likely Range)',
                    line=dict(color='rgba(31,119,180,0.2)'), 
                    fillcolor='rgba(31,119,180,0.2)',
                    hovertemplate='<b>95%% Confidence Range</b><br>' +
                                  'Time: %{x|%Y-%m-%d %H:%M}<br>' +
                                  'Range: %{y:.1f} comms/min<br>' +
                                  '<extra></extra>'
                ))
                
                # 80% confidence interval (inner band)
                fig.add_trace(go.Scatter(
                    x=plot_df['timestamp_est'], 
                    y=plot_df['pi80_high'],
                    mode='lines', 
                    line=dict(color='rgba(255,127,14,0)'), 
                    showlegend=False,
                    hoverinfo='skip'
                ))
                fig.add_trace(go.Scatter(
                    x=plot_df['timestamp_est'], 
                    y=plot_df['pi80_low'],
                    fill='tonexty', 
                    mode='lines', 
                    name='80% Confidence (Expected Range)',
                    line=dict(color='rgba(255,127,14,0.35)'), 
                    fillcolor='rgba(255,127,14,0.35)',
                    hovertemplate='<b>80%% Confidence Range</b><br>' +
                                  'Time: %{x|%Y-%m-%d %H:%M}<br>' +
                                  'Range: %{y:.1f} comms/min<br>' +
                                  '<extra></extra>'
                ))
                
                # Forecast mean (predicted line)
                fig.add_trace(go.Scatter(
                    x=plot_df['timestamp_est'], 
                    y=plot_df['mean'],
                    mode='lines', 
                    name='🔮 Predicted Average',
                    line=dict(color='#1f77b4', width=3),
                    hovertemplate='<b>Forecast</b><br>' +
                                  'Time: %{x|%Y-%m-%d %H:%M}<br>' +
                                  'Expected: %{y:.1f} comms/min<br>' +
                                  '<extra></extra>'
                ))
                
                fig.update_layout(
                    title="<b>ATC Communication Rate: Historical Data + Future Prediction</b>",
                    xaxis_title="<b>Time</b>",
                    yaxis_title="<b>Radio Communication Detections per Minute</b>",
                    height=500,
                    hovermode='x unified',
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01,
                        bgcolor='rgba(255,255,255,0.8)'
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Add explanation below graph
                st.caption("""
                📊 **How to read this graph:**
                - **Dark line (left side)**: Actual past communication rates we observed
                - **Blue line (right side)**: Our prediction of future communication rates
                - **Colored bands**: Confidence ranges - wider bands mean more uncertainty
                  - **Orange band (narrower)**: 80% confident actual rate will fall in this range
                  - **Blue band (wider)**: 95% confident actual rate will fall in this range
                """)
                
                # Display key metrics
                st.markdown("---")
                st.markdown("### 📊 Key Forecast Insights")
                
                col1, col2, col3 = st.columns(3)
                
                # Calculate metrics
                near_term_mean = float(fcst['mean'].head(min(10, len(fcst))).mean())
                risk = _poisson_tail_normal_approx(int(threshold), float(lam) * (bias_factor if bias_on else 1.0), float(phi))
                risk_pct = risk * 100.0
                hist_baseline = float(np.percentile(hist.values, 75)) if len(hist) > 0 else near_term_mean
                
                with col1:
                    st.metric(
                        "Expected Communication Rate",
                        f"{int(round(near_term_mean))} per min",
                        help="Average predicted radio communication detections per minute for the next 10 minutes"
                    )

                    # Add popup messages based on expected rate vs threshold
                    if near_term_mean < threshold:
                        st.success("🍹 **Grab a coke and relax!** Light traffic expected ahead.")
                    elif near_term_mean >= threshold:
                        st.warning("⚡ **You are entering a busy window!** Prepare for increased communication volume.")
                
                with col2:
                    alert_color = "🔴" if risk_pct >= 90 else "🟡" if risk_pct >= 70 else "🟢"
                    st.metric(
                        f"{alert_color} Risk of Exceeding {threshold}/min", 
                        f"{risk_pct:.0f}%",
                        delta="High Risk" if risk_pct >= 90 else "Moderate Risk" if risk_pct >= 70 else "Low Risk",
                        delta_color="off",
                        help=f"Probability that communication rate will exceed {threshold} per minute"
                    )
                
                with col3:
                    if near_term_mean >= hist_baseline:
                        traffic_status = "🔴 Busy"
                        traffic_delta = "Higher than typical"
                    else:
                        traffic_status = "🟢 Normal"
                        traffic_delta = "Within normal range"
                    
                    st.metric(
                        "Traffic Status", 
                        traffic_status,
                        delta=traffic_delta,
                        delta_color="off",
                        help=f"Compared to 75th percentile baseline ({hist_baseline:.1f} comms/min)"
                    )
                
                # Natural-language summary
                if risk_pct >= 90.0:
                    st.error(f"🚨 **High Traffic Alert**: Very high probability ({risk_pct:.0f}%) of exceeding {threshold} communication detections per minute. Expect a busy period.")
                elif risk_pct >= 70.0:
                    st.warning(f"⚠️ **Moderate Traffic**: {risk_pct:.0f}% chance of exceeding {threshold} communication detections per minute. Traffic may pick up.")
                else:
                    st.info(f"✅ **Normal Traffic**: Expecting around {int(round(near_term_mean))} communication detections per minute. {risk_pct:.0f}% chance of exceeding {threshold}/min threshold.")
                
                # Technical details in expander
                with st.expander("🔧 Technical Forecast Parameters"):
                    st.write(f"- **λ (lambda)**: {lam:.3f} - Base rate (average communication detections per minute)")
                    st.write(f"- **φ (phi)**: {phi:.3f} - Dispersion factor (variance/mean ratio)")
                    st.write(f"- **Bias correction factor**: {bias_factor:.3f} - Adjustment for recent trends")
                    st.write(f"- **Historical baseline (75th percentile)**: {hist_baseline:.2f} comms/min")
                
                # Backtest
                st.markdown("---")
                st.subheader("✅ Model Validation: How Accurate Are Our Predictions?")
                st.caption("Testing forecast accuracy using historical data (rolling backtest with 1-minute ahead predictions)")
                bt = backtest_minute_forecast(minute_series, window_minutes=window, horizon=1, test_minutes=min(horizon*6, 1440))
                if bt is None:
                    st.info("Not enough history for backtesting yet.")
                else:
                    colm1, colm2, colm3 = st.columns(3)
                    with colm1:
                        st.metric(
                            "Average Error", 
                            f"{bt['mae']:.2f} comms/min",
                            help="Mean Absolute Error (MAE): Average difference between predicted and actual communication detections per minute. Lower is better."
                        )
                    with colm2:
                        mase_val = bt['mase_vs_naive']
                        mase_delta = "Better than naive" if mase_val < 1 else "Worse than naive"
                        st.metric(
                            "Model vs Simple Guess", 
                            f"{mase_val:.2f}",
                            delta=mase_delta,
                            delta_color="inverse",
                            help="MASE (Mean Absolute Scaled Error): Compares model to a naive 'last value' prediction. < 1.0 means our model beats the simple approach."
                        )
                    with colm3:
                        st.metric(
                            "Prediction Intervals Hit Rate", 
                            f"{bt['pi80_coverage']*100:.0f}% / {bt['pi95_coverage']*100:.0f}%",
                            help="Shows how often actual values fell within our 80% and 95% confidence intervals. Should be close to 80% and 95% respectively."
                        )
                    
                    # Predicted vs actual scatter with improved labeling
                    bt_df = pd.DataFrame({
                        'Predicted Communications': bt['preds'], 
                        'Actual Communications': bt['trues']
                    })
                    
                    fig_bt = px.scatter(
                        bt_df, 
                        x='Predicted Communications', 
                        y='Actual Communications',
                        title="<b>Model Accuracy: Predicted vs Actual Communication Detections per Minute</b>",
                        labels={
                            'Predicted Communications': 'Predicted Communication Detections per Minute',
                            'Actual Communications': 'Actual Communication Detections per Minute'
                        }
                    )
                    
                    # Add perfect prediction line (diagonal)
                    max_val = max(bt_df['Predicted Communications'].max(), bt_df['Actual Communications'].max())
                    fig_bt.add_shape(
                        type='line', 
                        x0=0, y0=0, 
                        x1=max_val, y1=max_val, 
                        line=dict(color='red', dash='dash', width=2),
                        name='Perfect Prediction'
                    )
                    
                    # Add annotation for the diagonal line
                    fig_bt.add_annotation(
                        x=max_val * 0.7,
                        y=max_val * 0.75,
                        text="Perfect predictions<br>would fall on this line",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=2,
                        arrowcolor='red',
                        ax=-40,
                        ay=-40,
                        font=dict(size=10, color='red'),
                        bgcolor='rgba(255,255,255,0.8)',
                        bordercolor='red',
                        borderwidth=1
                    )
                    
                    fig_bt.update_layout(
                        height=450,
                        xaxis_title="<b>Predicted Communication Detections per Minute</b>",
                        yaxis_title="<b>Actual Communication Detections per Minute</b>",
                        showlegend=False,
                        hovermode='closest'
                    )
                    
                    fig_bt.update_traces(
                        marker=dict(size=8, opacity=0.6, color='steelblue'),
                        hovertemplate='<b>Prediction Quality</b><br>' +
                                      'Predicted: %{x:.1f} comms/min<br>' +
                                      'Actually Observed: %{y:.1f} comms/min<br>' +
                                      '<extra></extra>'
                    )
                    
                    st.plotly_chart(fig_bt, use_container_width=True)
                    
                    # Add interpretation guide
                    st.caption("""
                    📊 **How to read this graph:**
                    - Each point represents one forecast made by the model
                    - Points close to the red diagonal line = accurate predictions
                    - Points above the line = model under-predicted (actual was higher)
                    - Points below the line = model over-predicted (actual was lower)
                    - Tighter clustering around the line = better model accuracy
                    """)
                
                with st.expander("Method & Assumptions"):
                    st.markdown(
                        "- Forecast = recent mean per-minute rate with optional short-term bias factor; uncertainty widened using dispersion φ=Var/Mean.\n"
                        "- Intervals: 80% and 95% normal-approx with Var=φ·μ. Exceedance uses continuity-corrected normal tail.\n"
                        "- Backtest: rolling origin, 1-minute horizon; MAE/MASE vs lag-1 naive; empirical coverage reported.\n"
                        "- Guidance: Exceedance > 90% indicates strong likelihood of an operational surge.")
    
    # Footer
    st.markdown("---")
    current_year = datetime.now().year
    st.markdown(
        f"""
        <div style='text-align: center; color: #666;'>
            🛫 CATSR Live Communications Dashboard © {current_year} All rights reserved.
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
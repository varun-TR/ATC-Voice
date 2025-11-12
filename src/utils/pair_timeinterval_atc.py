#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pair ATC <-> Pilot communications and measure response time.

- Expects a JSON with structure:
  {
    "items": [
      {
        "chunk_number": ...,
        "timestamp_utc": "2025-10-18T18:56:19.820190+00:00",
        "raw_transcription": "Ring Net Forty Six Zero Nine ..."
      },
      ...
    ]
  }

Outputs to --outdir:
  - pairs.csv: matched exchanges with delta_sec and direction
  - orphans.csv: utterances that didn’t find a partner
  - summary.json: counts + trimmed stats (p50, p90, etc.)
  - pair_timeinterval_atc.log: processing log
"""

import argparse, json, os, re, math, csv, statistics, sys, pathlib, datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# ====== Configurable dictionaries (ICAO/FAA-informed) ======
# Source inspirations: ICAO Doc 9432 (Manual of Radiotelephony), FAA JO 7110.65 phraseology
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
# Airline & unit hints (minimal seed list; extend as needed)
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
# Words/symbols that indicate non-speech/noise
JUNK_PAT = re.compile(r"^[\W_\.]+$")

# ====== Lightweight token utils ======
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

# ====== Data structures ======
@dataclass
class Utt:
    idx: int
    ts: float       # epoch seconds
    text: str
    text_clean: str
    callsign: Optional[str]
    role: str       # "ATC" or "PILOT"

# ====== Pipeline ======
def parse_time(ts_utc: str) -> float:
    # robust parse; Python 3.12+ supports fromisoformat with TZ
    return datetime.datetime.fromisoformat(ts_utc).timestamp()

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

def load_items(path_json: str) -> List[Dict]:
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    return items

def preprocess(items: List[Dict]) -> List[Utt]:
    out: List[Utt] = []
    for i, it in enumerate(items):
        raw = normalize_text(it.get("raw_transcription",""))
        if is_junk(raw): 
            continue
        norm = lower_letters_digits(raw)
        norm = expand_nato_numbers(norm)
        cs = looks_like_callsign(norm)
        role = label_role(norm, cs is not None)
        try:
            ts = parse_time(it["timestamp_utc"])
        except Exception:
            # if no timestamp, skip
            continue
        out.append(Utt(idx=i, ts=ts, text=raw, text_clean=norm, callsign=cs, role=role))
    # temporal sort
    out.sort(key=lambda u: u.ts)
    return out

def same_flight(a: Utt, b: Utt) -> bool:
    if a.callsign and b.callsign:
        return a.callsign == b.callsign
    # fallback: soft match if both have digits and share at least 3 aligned characters
    return False

def direction(a: Utt, b: Utt) -> str:
    # decide who answered whom
    if a.role == "ATC" and b.role == "PILOT":
        return "ATC_to_PILOT"
    if a.role == "PILOT" and b.role == "ATC":
        return "PILOT_to_ATC"
    # fallback to alternation by time
    return "ATC_to_PILOT" if a.ts < b.ts else "PILOT_to_ATC"

def pair_utts(utts: List[Utt], base_window: float = 12.0, grace: float = 2.0) -> Tuple[List[Dict], List[Utt]]:
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
            if dt <= base_window or (dt <= base_window + grace and score >= 4.0):
                if score > best_score:
                    best_score, best = score, (j, v, dt)

        if best is not None:
            j, v, dt = best
            used.add(i); used.add(j)
            d = direction(u, v)
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

def stats(values: List[float]) -> Dict[str, float]:
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

def write_csv(path, rows, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to transcripts JSON (items[].raw_transcription)")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--window", type=float, default=12.0, help="Base pairing window in seconds")
    ap.add_argument("--device", default="cpu", help="Device label (e.g., 'cuda:0' or 'cpu')")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    log_path = os.path.join(args.outdir, "pair_timeinterval_atc.log")
    with open(log_path, "w") as log:
        log.write("Starting …\n")

    print("[1/6] Loading JSON …")
    items = load_items(args.input)
    print(f"Loaded {len(items)} items.")

    print("[2/6] Cleaning & preprocessing …")
    utts = preprocess(items)
    print(f"Kept {len(utts)} utterances.")

    # (Optional) At this point you can load a HuggingFace pipeline for NER,
    # but we rely on robust regex + keyword scoring to avoid extra installs.

    print("[5/6] Pairing communications …")
    pairs, orphans = pair_utts(utts, base_window=args.window, grace=2.0)

    print("[6/6] Writing outputs …")
    # pairs
    pairs_path = os.path.join(args.outdir, "pairs.csv")
    pairs_hdr = ["i","j","t1_utc","t2_utc","delta_sec","dir","callsign","u_role","v_role","u_text","v_text"]
    write_csv(pairs_path, pairs, pairs_hdr)

    # orphans
    orph_path = os.path.join(args.outdir, "orphans.csv")
    orph_hdr = ["idx","ts_utc","role","callsign","text"]
    write_csv(orph_path, [
        {"idx":o.idx, "ts_utc":o.ts, "role":o.role, "callsign":o.callsign or "", "text":o.text}
        for o in orphans
    ], orph_hdr)

    # summary
    atc_to_p = [p["delta_sec"] for p in pairs if p["dir"]=="ATC_to_PILOT"]
    p_to_atc = [p["delta_sec"] for p in pairs if p["dir"]=="PILOT_to_ATC"]
    summary = {
        "total_pairs": len(pairs),
        "ATC_to_PILOT": stats(atc_to_p),
        "PILOT_to_ATC": stats(p_to_atc),
        "window_sec": args.window
    }
    with open(os.path.join(args.outdir,"summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Done.")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()

"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python -m pip install coqui-tts; python fix_local_clone_voices.py

What this does:
  1. Finds the audio you saved in C:\\jarvis-client\\voices for both ElevenLabs
     voices (matched by voice name, looked up through the ElevenLabs API --
     reading voice info costs no quota). If a voice has original sample
     recordings, the longest one is used; otherwise the preview clip.
  2. Converts each to a WAV reference file (ref_normal.wav, ref_evil.wav).
  3. Patches voice_assistant.py so replies are spoken by XTTS v2 (a local
     voice-cloning model) using those references. "Evil assistant" mode uses
     the evil reference, "normal assistant" the normal one.
  4. Sets TTS_ENGINE=clone in .env.

Notes:
  - Runs fully offline after the one-time model download (about 2 GB).
  - XTTS v2 is licensed under the Coqui Public Model License (non-commercial).
    The script asks you to accept it before continuing.
  - Cloning quality depends on the reference audio. A few seconds of preview
    gives a rough match, not an exact copy. Original samples sound better.
  - On CPU, each reply can take several seconds to generate. A GPU is faster.
  - If it is too slow, set TTS_ENGINE=edge in .env to go back to Edge TTS.
    TTS_ENGINE=elevenlabs uses ElevenLabs again once quota is available.

Requires fix_edge_tts.py to be applied first.
Idempotent: safe to re-run.
"""

import glob
import json
import os
import re
import shutil
import sys
import time

import requests
import soundfile as sf
from dotenv import dotenv_values

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, "voice_assistant.py")
ENV_PATH = os.path.join(BASE, ".env")
VOICES_DIR = os.path.join(BASE, "voices")
MARKER = "CLONE VOICE PATCH"
FN_ANCHOR = (
    '    """Speak with Edge TTS; if that fails, use the built-in Windows voice."""\n'
    "    text = _cap_spoken(text)\n"
)
FN_DEF = "def _local_tts_fallback(text):\n"
MAX_REF_SECONDS = 25

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Clone voice patch already present. Nothing to do.")
    raise SystemExit(0)

if "EDGE TTS PATCH" not in src or src.count(FN_ANCHOR) != 1 or src.count(FN_DEF) != 1:
    print("The earlier fix_edge_tts.py patch is not applied (or was edited).")
    print("Run it first, then re-run this script.")
    raise SystemExit(1)

print("XTTS v2 is licensed under the Coqui Public Model License (non-commercial use).")
print("Only continue if that fits how you will use Helix.")
if input("Type yes to accept and continue: ").strip().lower() != "yes":
    print("Cancelled. Nothing changed.")
    raise SystemExit(1)

# --- 1. Match saved audio to each voice ------------------------------------
env = dotenv_values(ENV_PATH)
api_key = (env.get("ELEVENLABS_API_KEY") or "").strip().strip('"')
voice_ids = {
    "normal": (env.get("ELEVENLABS_VOICE_ID") or "VVPC9ZEO8FNTR5UKIDv8").strip().strip('"'),
    "evil": (env.get("ELEVENLABS_VOICE_ID_EVIL") or "cxBcSUO2wRQX14onLPZI").strip().strip('"'),
}

audio_files = [
    p for p in glob.glob(os.path.join(VOICES_DIR, "*"))
    if p.lower().endswith((".mp3", ".wav", ".flac", ".ogg", ".m4a"))
    and not os.path.basename(p).lower().startswith("ref_")
]
if not audio_files:
    print(f"No audio files found in {VOICES_DIR}. Save the voices there first.")
    raise SystemExit(1)

refs = {}
for role, vid in voice_ids.items():
    r = requests.get(
        f"https://api.elevenlabs.io/v1/voices/{vid}",
        headers={"xi-api-key": api_key},
        timeout=20,
    )
    r.raise_for_status()
    name = r.json().get("name", "")
    matches = [p for p in audio_files if os.path.basename(p).lower().startswith(name.lower())]
    if not matches:
        print(f"No saved audio starts with the voice name '{name}' ({role}).")
        print("Files found:", [os.path.basename(p) for p in audio_files])
        raise SystemExit(1)
    best = max(matches, key=os.path.getsize)

    data, rate = sf.read(best)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data[: int(rate * MAX_REF_SECONDS)]
    out_path = os.path.join(VOICES_DIR, f"ref_{role}.wav")
    sf.write(out_path, data, rate)
    refs[role] = out_path
    print(f"{role}: '{name}' -> {os.path.basename(best)} ({len(data) / rate:.1f}s) -> ref_{role}.wav")

with open(os.path.join(VOICES_DIR, "clone_map.json"), "w", encoding="utf-8") as f:
    json.dump(refs, f)

# --- 2. Patch voice_assistant.py -------------------------------------------
shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

# Find the variable that holds the currently selected voice ID, by looking
# for an assignment of the evil voice constant inside the voice-switch code.
evil_var = None
for m in re.finditer(r"^[ \t]+(\w+)\s*=\s*\w*EVIL\w*\s*$", src, re.MULTILINE):
    if "evil" not in m.group(1).lower():
        evil_var = m.group(1)
        break
if evil_var is None:
    print("Could not detect the evil-voice switch variable. Normal voice will be used for both modes.")

block = f'''# === {MARKER} ===
import threading as _clone_threading

_CLONE_EVIL_VAR = {evil_var!r}
_xtts_holder = {{"model": None}}
_xtts_lock = _clone_threading.Lock()

def _clone_is_evil():
    if not _CLONE_EVIL_VAR:
        return False
    evil_id = _tts_os.environ.get("ELEVENLABS_VOICE_ID_EVIL")
    return bool(evil_id) and globals().get(_CLONE_EVIL_VAR) == evil_id

def _get_xtts():
    with _xtts_lock:
        if _xtts_holder["model"] is None:
            import torch
            from TTS.api import TTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print("[Helix] Loading cloned-voice model (first load is slow)...")
            _xtts_holder["model"] = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            print("[Helix] Cloned-voice model ready.")
        return _xtts_holder["model"]

def _clone_speak(text):
    import json
    import tempfile
    import pygame
    base = _tts_os.path.dirname(_tts_os.path.abspath(__file__))
    with open(_tts_os.path.join(base, "voices", "clone_map.json"), encoding="utf-8") as f:
        refs = json.load(f)
    if _xtts_holder["model"] is None and _xtts_lock.locked():
        raise RuntimeError("cloned-voice model is still loading")
    ref = refs["evil"] if (_clone_is_evil() and refs.get("evil")) else refs["normal"]
    out = _tts_os.path.join(tempfile.gettempdir(), "helix_clone_tts.wav")
    _get_xtts().tts_to_file(text=text, speaker_wav=ref, language="en", file_path=out)
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(out)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(50)
    pygame.mixer.music.unload()

def _clone_preload():
    try:
        _get_xtts()
    except Exception as preload_err:
        print(f"[Helix] Cloned-voice model failed to load: {{preload_err}}")

if _tts_os.environ.get("TTS_ENGINE", "edge").lower() == "clone":
    _clone_threading.Thread(target=_clone_preload, daemon=True).start()
# === END {MARKER} ===

'''

call = (
    FN_ANCHOR
    + '    if _tts_os.environ.get("TTS_ENGINE", "edge").lower() == "clone":\n'
    + "        try:\n"
    + "            _clone_speak(text)\n"
    + "            return\n"
    + "        except Exception as clone_err:\n"
    + '            print(f"[Helix] Cloned voice failed, using Edge TTS: {clone_err}")\n'
)

src = src.replace(FN_ANCHOR, call, 1)
src = src.replace(FN_DEF, block + FN_DEF, 1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

# --- 3. Update .env ----------------------------------------------------------
with open(ENV_PATH, "r", encoding="utf-8") as f:
    lines = [l.rstrip("\n") for l in f]
lines = [l for l in lines if not re.match(r"^(TTS_ENGINE|COQUI_TOS_AGREED)=", l)]
lines += ["TTS_ENGINE=clone", "COQUI_TOS_AGREED=1"]
with open(ENV_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print()
print("Done. Restart voice_assistant.py.")
print("First start downloads the XTTS model (about 2 GB) and loads it in the")
print("background. Until it is ready, replies use Edge TTS automatically.")

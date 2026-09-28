"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python -m pip install edge-tts pygame; python fix_edge_tts.py

Makes Edge TTS the main voice for Helix's replies. Edge TTS is free, needs
no API key and has no character quota. Default voice is a natural female
voice (en-US-AriaNeural).

Behavior after this patch:
  - Replies are spoken with Edge TTS. ElevenLabs is skipped entirely.
  - If Edge TTS fails (for example no internet), Helix falls back to the
    built-in Windows voice (female Zira if installed).
  - To go back to ElevenLabs later (after the quota resets or a plan
    upgrade), add this line to C:\\jarvis-client\\.env and restart:
        TTS_ENGINE=elevenlabs
  - To change the Edge voice, add a line such as:
        EDGE_VOICE=en-US-JennyNeural
    Other female options: en-US-AriaNeural, en-US-JennyNeural,
    en-GB-SoniaNeural, en-AU-NatashaNeural.

Note: the "evil assistant" voice switch only applies to ElevenLabs. While
Edge TTS is the engine, both modes use the same Edge voice.

Requires fix_tts_quota_fallback.py to be applied first.
Idempotent: safe to re-run.
"""

import re
import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "EDGE TTS PATCH"
PRIOR_MARKER = "TTS FALLBACK PATCH"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Edge TTS patch already present. Nothing to do.")
    raise SystemExit(0)

state_line = '_tts_state = {"eleven_disabled": False}'
fn_pattern = re.compile(
    r"def _local_tts_fallback\(text\):.*?(?=# === END " + re.escape(PRIOR_MARKER) + r" ===)",
    re.DOTALL,
)

if PRIOR_MARKER not in src or state_line not in src or not fn_pattern.search(src):
    print("The earlier fix_tts_quota_fallback.py patch is not applied (or was edited).")
    print("Run it first, then re-run this script.")
    raise SystemExit(1)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

# 1. Skip ElevenLabs unless TTS_ENGINE=elevenlabs is set in .env
new_state = (
    "import os as _tts_os\n"
    '_tts_state = {"eleven_disabled": _tts_os.environ.get("TTS_ENGINE", "edge").lower() != "elevenlabs"}'
)
src = src.replace(state_line, new_state, 1)

# 2. Allow longer spoken replies, since Edge TTS has no character quota
src = src.replace("_MAX_SPOKEN_CHARS = 300", "_MAX_SPOKEN_CHARS = 500", 1)

# 3. Replace the local fallback with Edge TTS first, Windows voice second
new_fn = f'''# === {MARKER} ===
def _edge_tts_speak(text):
    import asyncio
    import tempfile
    import edge_tts
    import pygame
    voice = _tts_os.environ.get("EDGE_VOICE", "en-US-AriaNeural")
    path = _tts_os.path.join(tempfile.gettempdir(), "helix_edge_tts.mp3")
    asyncio.run(edge_tts.Communicate(text, voice).save(path))
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(50)
    pygame.mixer.music.unload()

def _local_tts_fallback(text):
    """Speak with Edge TTS; if that fails, use the built-in Windows voice."""
    text = _cap_spoken(text)
    try:
        _edge_tts_speak(text)
        return
    except Exception as edge_err:
        print(f"[Helix] Edge TTS failed, using Windows voice: {{edge_err}}")
    try:
        import pyttsx3
        engine = pyttsx3.init()
        female_names = ("zira", "hazel", "susan", "aria", "jenny", "eva", "female")
        for v in engine.getProperty("voices"):
            if any(n in (v.name or "").lower() for n in female_names):
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
    except Exception as local_err:
        print(f"[Helix] Windows voice also failed: {{local_err}}")
# === END {MARKER} ===
'''
src = fn_pattern.sub(lambda _m: new_fn, src, count=1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}. Restart voice_assistant.py to pick it up.")
print("Edge TTS is now the main voice (female, en-US-AriaNeural).")
print("Switch back to ElevenLabs any time by adding TTS_ENGINE=elevenlabs to .env.")

"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python -m pip install pyttsx3
    python fix_tts_quota_fallback.py

Problem: the ElevenLabs free tier allows 10,000 characters per month. Your
account shows 9,999 / 10,000 used, so ElevenLabs now answers every TTS
request with 401 (quota exceeded). Long replies (like a 100-line answer)
burn the quota very quickly.

This patch, applied on top of the earlier "ROBUST SPEAK PATCH":
  1. Caps what gets SPOKEN to about 300 characters (cut at a sentence end).
     The full reply still prints in the console and the dashboard -- only
     the audio is shortened, so the quota lasts far longer.
  2. If ElevenLabs fails for any reason, Helix speaks the reply with the
     built-in Windows voice (pyttsx3 / SAPI) instead of going silent.
  3. After the first 401, ElevenLabs is skipped for the rest of the session,
     so there are no repeated failing requests or retry delays.

Idempotent: safe to re-run.
"""

import re
import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "TTS FALLBACK PATCH"
PRIOR_MARKER = "ROBUST SPEAK PATCH"
FAIL_LINE = 'print(f"[Helix] TTS request failed after retries, skipping this reply: {e}")'

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("TTS fallback patch already present. Nothing to do.")
    raise SystemExit(0)

if PRIOR_MARKER not in src or FAIL_LINE not in src:
    print("The earlier fix_speak_crash.py patch is not applied (or was edited).")
    print("Run fix_speak_crash.py first, then re-run this script.")
    raise SystemExit(1)

m = re.search(r"^def speak\(\s*([A-Za-z_][A-Za-z0-9_]*)", src, re.MULTILINE)
if not m:
    print("Could not find 'def speak(...)' in voice_assistant.py. No changes made.")
    raise SystemExit(1)
text_param = m.group(1)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

helpers = f'''# === {MARKER} ===
_tts_state = {{"eleven_disabled": False}}
_MAX_SPOKEN_CHARS = 300

def _cap_spoken(text):
    """Shorten text for audio only, cutting at a sentence end when possible."""
    if len(text) <= _MAX_SPOKEN_CHARS:
        return text
    cut = text[:_MAX_SPOKEN_CHARS]
    last_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_end > 80:
        cut = cut[: last_end + 1]
    return cut.rstrip()

def _local_tts_fallback(text):
    """Speak with the built-in Windows voice when ElevenLabs is unavailable."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(_cap_spoken(text))
        engine.runAndWait()
    except Exception as local_err:
        print(f"[Helix] Local voice also failed: {{local_err}}")
# === END {MARKER} ===

'''

# Insert helpers right before the speak() definition.
src = src[: m.start()] + helpers + src[m.start():]

# At the top of the (already wrapped) speak body: cap the text and short-circuit
# to the local voice once ElevenLabs has been marked unavailable.
entry_anchor = f"    # === {PRIOR_MARKER} ===\n"
entry_code = (
    entry_anchor
    + f"    {text_param}_full = {text_param}\n"
    + f"    {text_param} = _cap_spoken({text_param})\n"
    + '    if _tts_state["eleven_disabled"]:\n'
    + f"        _local_tts_fallback({text_param})\n"
    + "        return None\n"
)
assert src.count(entry_anchor) == 1
src = src.replace(entry_anchor, entry_code, 1)

# In the failure handler: mark ElevenLabs unavailable on auth/quota errors,
# then speak with the local voice instead of staying silent.
fail_replacement = (
    FAIL_LINE + "\n"
    + '        if "401" in str(e) or "quota" in str(e).lower():\n'
    + '            _tts_state["eleven_disabled"] = True\n'
    + '            print("[Helix] ElevenLabs unavailable (quota or auth). Using local voice for this session.")\n'
    + f"        _local_tts_fallback({text_param})"
)
assert src.count(FAIL_LINE) == 1
src = src.replace(FAIL_LINE, fail_replacement, 1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}. Restart voice_assistant.py to pick it up.")
print("Spoken replies are now capped at ~300 characters; the full text still")
print("shows in the console and dashboard.")
print("ElevenLabs free-tier quota resets monthly (your account shows the reset")
print("date around Oct 20). Until then Helix uses the local Windows voice.")

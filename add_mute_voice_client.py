"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python add_mute_voice_client.py

Patches voice_assistant.py so Helix:
  - Recognizes the spoken/typed phrase "mute yourself" / "unmute yourself" as a
    direct command (no LLM round-trip needed) and calls the backend's
    /mute/on or /mute/off.
  - Polls /mute/status in the background every ~0.5s.
  - Skips starting any new TTS playback while muted.
  - Immediately stops audio that's already playing the moment mute turns on
    (requires pygame.mixer for playback -- if you're using something else,
    see the NOTE at the bottom of this script for what to change).

Idempotent: safe to re-run.
"""

import re
import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "MUTE FEATURE"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Mute feature already present. Nothing to do.")
    raise SystemExit(0)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

mute_block = '''
# === MUTE FEATURE ===
import threading as _mute_threading
import requests as _mute_requests

_mute_state = {"muted": False}
_mute_lock = _mute_threading.Lock()

def _mute_get_base_url():
    # Reuse whatever base URL / token the rest of this client already uses.
    try:
        return API_BASE_URL  # noqa: F821  (expected to exist elsewhere in this file)
    except NameError:
        return "http://127.0.0.1:8000"

def _mute_get_token():
    try:
        return HELIX_API_TOKEN  # noqa: F821
    except NameError:
        import os
        return os.environ.get("HELIX_API_TOKEN", "")

def is_muted():
    with _mute_lock:
        return _mute_state["muted"]

def _mute_poll_loop():
    base = _mute_get_base_url()
    while True:
        try:
            r = _mute_requests.get(f"{base}/mute/status", timeout=2)
            if r.ok:
                new_val = bool(r.json().get("muted", False))
                with _mute_lock:
                    was_muted = _mute_state["muted"]
                    _mute_state["muted"] = new_val
                if new_val and not was_muted:
                    _mute_stop_playback()
        except Exception:
            pass
        time.sleep(0.5)

def _mute_stop_playback():
    # NOTE: this assumes TTS audio is played with pygame.mixer.music.
    # If this client plays audio a different way (playsound, winsound, simpleaudio,
    # etc.), replace the body of this function with that library's stop call.
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass

def set_mute(muted: bool):
    base = _mute_get_base_url()
    token = _mute_get_token()
    endpoint = "/mute/on" if muted else "/mute/off"
    try:
        _mute_requests.post(
            f"{base}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
    except Exception:
        pass
    with _mute_lock:
        _mute_state["muted"] = muted
    if muted:
        _mute_stop_playback()

def handle_mute_voice_command(text: str) -> bool:
    """Call this early in your command-handling flow, before sending text to the
    LLM. Returns True if the text was a mute/unmute command (and was handled),
    False otherwise -- so you know whether to continue normal processing."""
    normalized = text.strip().lower()
    if normalized in ("mute yourself", "mute"):
        set_mute(True)
        print("[Helix] Muted.")
        return True
    if normalized in ("unmute yourself", "unmute"):
        set_mute(False)
        print("[Helix] Unmuted.")
        return True
    return False

_mute_poll_thread = _mute_threading.Thread(target=_mute_poll_loop, daemon=True)
_mute_poll_thread.start()
# === END MUTE FEATURE ===
'''

src = src.rstrip() + "\n" + mute_block

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}.")
print()
print("Two things left for you to wire in by hand, since I don't have your exact")
print("command-handling and TTS-playback code in this file:")
print()
print("1. Wherever you currently take the recognized speech/typed text and decide")
print('   what to do with it, add near the top:')
print()
print("       if handle_mute_voice_command(user_text):")
print("           continue  # or return, depending on your loop structure")
print()
print("2. Wherever you call ElevenLabs TTS and play the resulting audio, wrap it:")
print()
print("       if not is_muted():")
print("           speak(reply_text)   # your existing TTS+playback call")
print()
print("3. If your playback isn't pygame.mixer.music, edit _mute_stop_playback()")
print("   in this file to call your audio library's stop function instead.")

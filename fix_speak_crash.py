"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python fix_speak_crash.py

Problem: a single network hiccup talking to ElevenLabs (TLS connection reset,
timeout, etc.) raises an unhandled exception inside speak(), which kills the
entire voice_assistant.py process -- you have to manually restart it.

Fix, applied to the existing speak() function in voice_assistant.py:
  1. The outbound request now goes through a requests.Session with automatic
     retries (3 attempts, short exponential backoff) for exactly this class
     of transient error (connection reset, timeout, common 5xx codes) --
     most of these clear up on the very next attempt.
  2. The entire function body is wrapped in try/except. If every retry still
     fails, Helix logs it to the console and returns instead of raising, so
     the assistant keeps running and is ready for your next command --
     it just silently skips speaking that one reply instead of crashing.

Idempotent: safe to re-run.
"""

import re
import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "ROBUST SPEAK PATCH"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Robust speak() patch already present. Nothing to do.")
    raise SystemExit(0)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

# --- Locate the existing `def speak(...):` function and its body -----------
m = re.search(r"^def speak\([^)]*\):\n", src, re.MULTILINE)
if not m:
    print("Could not find 'def speak(...):' in voice_assistant.py.")
    print("No changes made -- open the file and share the speak() function")
    print("if you'd like this scripted instead of applied by hand.")
    raise SystemExit(1)

def_start = m.start()
body_start = m.end()

lines = src[body_start:].split("\n")
body_lines = []
i = 0
for line in lines:
    if line.strip() == "":
        body_lines.append(line)
        i += 1
        continue
    indent = len(line) - len(line.lstrip())
    if indent == 0 and body_lines:  # dedent back to column 0 -> function ended
        break
    body_lines.append(line)
    i += 1
body_text = "\n".join(body_lines)
body_end = body_start + len(body_text)

if not body_text.strip():
    print("speak() appears to have an empty body -- aborting to avoid breaking it.")
    raise SystemExit(1)

# Re-indent the original body one level deeper so it sits inside try:
reindented = "\n".join(("    " + l if l.strip() else l) for l in body_lines)

new_body = f'''    # === {MARKER} ===
    import time as _speak_time
    from requests.adapters import HTTPAdapter
    try:
        from urllib3.util.retry import Retry
    except ImportError:
        from requests.packages.urllib3.util.retry import Retry

    _speak_session = requests.Session()
    _speak_retry = Retry(
        total=3, backoff_factor=0.8,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
    )
    _speak_session.mount("https://", HTTPAdapter(max_retries=_speak_retry))
    _speak_session.mount("http://", HTTPAdapter(max_retries=_speak_retry))
    # Inside the original body below, `requests.post(...)` and `requests.get(...)`
    # calls now go through this retrying session instead.
    requests_orig_post, requests_orig_get = requests.post, requests.get
    requests.post, requests.get = _speak_session.post, _speak_session.get
    try:
{reindented}
    except Exception as e:
        print(f"[Helix] TTS request failed after retries, skipping this reply: {{e}}")
        return None
    finally:
        requests.post, requests.get = requests_orig_post, requests_orig_get
    # === END {MARKER} ===
'''

src = src[:def_start] + m.group(0) + new_body + src[body_end:]

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}.")
print()
print("speak() now retries transient network failures automatically, and if")
print("every retry still fails, it logs the error and returns instead of")
print("crashing the assistant. Restart voice_assistant.py to pick this up.")
print()
print("If this keeps happening (not just a one-off), it's usually one of:")
print("  - antivirus/firewall doing HTTPS inspection and resetting the")
print("    connection to api.elevenlabs.io")
print("  - a flaky network link")
print("  - the ElevenLabs API key being rate-limited or invalid")
print("Worth also rotating the ElevenLabs key you pasted in chat earlier --")
print("it's been exposed in plaintext and should be treated as compromised.")

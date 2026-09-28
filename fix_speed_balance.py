path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

changed = []

old = 'MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")'
new = 'MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")'
if old in src:
    src = src.replace(old, new, 1)
    changed.append("whisper model base -> small (better accents/natural speech, still faster than medium/large)")
elif "small" in src.split('MODEL_SIZE')[1][:60] if 'MODEL_SIZE' in src else False:
    pass

open(path, "w", encoding="utf-8").write(src)
print("DONE.")
for c in changed:
    print(" -", c)
if not changed:
    print(" (already on 'small' or pattern not found - check manually)")

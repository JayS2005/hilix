path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

old = '"zoom": "Zoom",'
new = '"zoom": "Zoom",\n    "whatsapp": "start whatsapp:",'

if "whatsapp" in src:
    print("already present, skipping")
else:
    assert old in src, "anchor not found"
    src = src.replace(old, new, 1)
    open(path, "w", encoding="utf-8").write(src)
    print("fixed")

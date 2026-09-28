path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

old = '"zoom": "Zoom",'
additions = [
    ("file manager", "explorer"),
    ("files", "explorer"),
    ("cherrytree", "cherrytree"),
    ("cherry tree", "cherrytree"),
]

changed = False
for key, cmd in additions:
    line = f'"{key}": "{cmd}",'
    if key not in src:
        old = old  # keep anchor, insert after zoom entry
        src = src.replace('"zoom": "Zoom",', f'"zoom": "Zoom",\n    {line}', 1)
        changed = True

if changed:
    open(path, "w", encoding="utf-8").write(src)
    print("patched")
else:
    print("nothing to add, already present")

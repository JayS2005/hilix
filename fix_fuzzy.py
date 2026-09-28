path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "import difflib" in src:
    print("already present, skipping")
else:
    # add import near top
    src = src.replace("import os, io, subprocess, requests",
                       "import os, io, subprocess, requests\nimport difflib", 1)

    old_func = '''def try_open_app(text_lower: str) -> bool:
    for name, cmd in WINDOWS_APP_WHITELIST.items():
        if name in text_lower:
            try:
                subprocess.Popen(cmd, shell=True)
                print(f"Launching: {name}")
            except Exception as e:
                print(f"Failed to launch {name}: {e}")
            return True
    return False'''

    new_func = '''def try_open_app(text_lower: str) -> bool:
    # 1. exact substring match first
    for name, cmd in WINDOWS_APP_WHITELIST.items():
        if name in text_lower:
            try:
                subprocess.Popen(cmd, shell=True)
                print(f"Launching: {name}")
            except Exception as e:
                print(f"Failed to launch {name}: {e}")
            return True

    # 2. fuzzy fallback: compare each word/phrase after "open" against whitelist keys
    words_after_open = text_lower.split("open", 1)[-1].strip()
    if not words_after_open:
        return False
    candidates = list(WINDOWS_APP_WHITELIST.keys())
    match = difflib.get_close_matches(words_after_open, candidates, n=1, cutoff=0.6)
    if match:
        name = match[0]
        cmd = WINDOWS_APP_WHITELIST[name]
        try:
            subprocess.Popen(cmd, shell=True)
            print(f"Launching (fuzzy match '{words_after_open}' -> '{name}'): {name}")
        except Exception as e:
            print(f"Failed to launch {name}: {e}")
        return True
    return False'''

    assert old_func in src, "anchor not found"
    src = src.replace(old_func, new_func, 1)
    open(path, "w", encoding="utf-8").write(src)
    print("patched")

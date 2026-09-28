path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "def _fuzzy_voice_switch" in src:
    print("already present, skipping")
else:
    if "import difflib" not in src:
        src = src.replace("import re", "import re\nimport difflib", 1)

    anchor = 'if "evil assistant" in text_lower:'
    helper = '''import difflib as _difflib_voice

def _fuzzy_voice_switch(text_lower):
    stripped = text_lower.replace("helix", "").strip()
    evil_ratio = _difflib_voice.SequenceMatcher(None, stripped, "evil assistant").ratio()
    normal_ratio = _difflib_voice.SequenceMatcher(None, stripped, "normal assistant").ratio()
    if evil_ratio >= 0.55 and evil_ratio >= normal_ratio:
        return "evil"
    if normal_ratio >= 0.55 and normal_ratio > evil_ratio:
        return "normal"
    return None


'''
    # This anchor is inside the main loop (evil assistant / normal assistant checks).
    # We replace those two exact-match blocks with a call to the fuzzy helper instead.
    old_block_start = 'if "evil assistant" in text.lower():'
    assert old_block_start in src, "voice switch anchor not found"

    # Insert helper function before main loop
    main_anchor = 'if __name__ == "__main__":'
    assert main_anchor in src, "main anchor not found"
    src = src.replace(main_anchor, helper + main_anchor, 1)

    old_full = '''if "evil assistant" in text.lower():
            current_voice[0] = ELEVEN_VOICE_EVIL
            print("Voice switched: EVIL")
            continue
        if "normal assistant" in text.lower():
            current_voice[0] = ELEVEN_VOICE_DEFAULT
            print("Voice switched: DEFAULT")
            continue'''
    new_full = '''_vswitch = _fuzzy_voice_switch(text.lower())
        if _vswitch == "evil":
            current_voice[0] = ELEVEN_VOICE_EVIL
            print("Voice switched: EVIL")
            continue
        if _vswitch == "normal":
            current_voice[0] = ELEVEN_VOICE_DEFAULT
            print("Voice switched: DEFAULT")
            continue'''
    assert old_full in src, "full voice-switch block not found"
    src = src.replace(old_full, new_full, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

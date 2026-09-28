path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "def open_start_menu" in src:
    print("already present, skipping")
else:
    anchor = "def try_open_app(text_lower: str) -> bool:"
    new_func = '''import ctypes
import time

def open_start_menu():
    VK_LWIN = 0x5B
    ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)  # key up
    print("Opened Start menu")

def try_open_app(text_lower: str) -> bool:'''
    assert anchor in src, "anchor not found"
    src = src.replace(anchor, new_func, 1)

    old_hook = 'if "open" in text.lower() and try_open_app(text.lower()):\n            continue'
    new_hook = '''if "start menu" in text.lower():
            open_start_menu()
            continue
        if "open" in text.lower() and try_open_app(text.lower()):
            continue'''
    assert old_hook in src, "hook anchor not found"
    src = src.replace(old_hook, new_hook, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

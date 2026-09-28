"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python add_close_app_feature.py

Adds a local (no-LLM-round-trip) handler for "close X" / "quit X" / "exit X" /
"kill X" commands, fuzzy-matched against a small, explicit whitelist -- the
same safety model as the existing app-open whitelist. It deliberately does
NOT let voice commands kill arbitrary process names; only apps in
CLOSE_APP_WHITELIST below can be closed this way.

Special case: "close file manager" does NOT taskkill explorer.exe. On modern
Windows, explorer.exe is also your desktop shell (taskbar + icons), so force-
killing it takes down your whole desktop, not just the open window. Instead
this sends a plain WM_CLOSE to just the File Explorer window(s), same as
clicking the X button.

Idempotent: safe to re-run.
"""

import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "CLOSE APP FEATURE"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Close-app feature already present. Nothing to do.")
    raise SystemExit(0)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

close_block = '''
# === CLOSE APP FEATURE ===
import difflib as _close_difflib
import subprocess as _close_subprocess
import ctypes as _close_ctypes

# Only these apps can be closed by voice. Add to this list deliberately --
# do not make it "close anything"; that turns a voice interface into a
# generic process-killer.
CLOSE_APP_WHITELIST = {
    "utorrent": ["uTorrent.exe"],
    "brave": ["brave.exe"],
    "cherrytree": ["cherrytree.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "outlook": ["OUTLOOK.EXE"],
    "onedrive": ["OneDrive.exe"],
    "onenote": ["ONENOTE.EXE"],
    "vscode": ["Code.exe"],
    "obsidian": ["Obsidian.exe"],
    "vlc": ["vlc.exe"],
    "telegram": ["Telegram.exe"],
    "signal": ["Signal.exe"],
    "zoom": ["Zoom.exe"],
    "whatsapp": ["WhatsApp.exe"],
    "notepad": ["notepad.exe"],
    "calc": ["CalculatorApp.exe", "calc.exe"],
}

_FILE_MANAGER_ALIASES = ["file manager", "explorer", "files", "file explorer"]

def _close_file_explorer_windows():
    """Closes open File Explorer windows without touching the explorer.exe
    shell process itself (killing that process would also kill your taskbar
    and desktop icons)."""
    WM_CLOSE = 0x0010
    user32 = _close_ctypes.windll.user32

    def enum_handler(hwnd, lparam):
        buf = _close_ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "CabinetWClass":  # File Explorer window class
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True

    EnumWindowsProc = _close_ctypes.WINFUNCTYPE(_close_ctypes.c_bool, _close_ctypes.c_int, _close_ctypes.c_int)
    user32.EnumWindows(EnumWindowsProc(enum_handler), 0)

def handle_close_app_command(text: str) -> bool:
    """Call this alongside your existing open-app handler, before sending
    text to the LLM. Returns True if it was a recognized close command
    (and was handled), False otherwise -- so you know whether to continue
    normal processing (including possibly falling through to the LLM)."""
    t = text.strip().lower()
    prefixes = ["close ", "quit ", "exit ", "kill "]
    prefix = next((p for p in prefixes if t.startswith(p)), None)
    if not prefix:
        return False
    target = t[len(prefix):].strip()
    if not target:
        return False

    if target in _FILE_MANAGER_ALIASES or _close_difflib.get_close_matches(target, _FILE_MANAGER_ALIASES, n=1, cutoff=0.55):
        _close_file_explorer_windows()
        print("[Helix] Closed File Explorer window(s).")
        return True

    keys = list(CLOSE_APP_WHITELIST.keys())
    match = _close_difflib.get_close_matches(target, keys, n=1, cutoff=0.55)
    if not match:
        return False  # not a recognized app -- let normal handling continue
    app_key = match[0]
    for proc in CLOSE_APP_WHITELIST[app_key]:
        _close_subprocess.run(["taskkill", "/IM", proc, "/F"], capture_output=True)
    print(f"[Helix] Closed {app_key}.")
    return True
# === END CLOSE APP FEATURE ===
'''

src = src.rstrip() + "\n" + close_block

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}.")
print()
print("One thing left to wire in by hand -- add this near where you already")
print("check for open-app commands (and the mute check, if you added that):")
print()
print("    if handle_close_app_command(user_text):")
print("        continue  # or return, depending on your loop structure")
print()
print("Note: closing chrome/edge/brave closes ALL windows and tabs for that")
print("browser at once, with no save prompts -- same as Task Manager > End Task.")
print("Add an app to CLOSE_APP_WHITELIST above if you want more than these covered.")

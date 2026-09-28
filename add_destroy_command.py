"""
Run on Windows, from C:\\jarvis-client, with the venv active:
    python add_destroy_command.py

Adds a "Destroy" voice/typed command that:
  1. Requires spoken/typed confirmation first (same pattern as your existing
     shutdown/restart/logoff commands) -- this is the single most destructive
     thing Helix can do, so it does not fire on one utterance.
  2. On confirmation: sends WM_CLOSE to visible top-level app windows (same
     as clicking the X on each -- unsaved-work dialogs still appear, nothing
     is force-killed), waits a few seconds, then shuts the machine down.

Idempotent: safe to re-run.
"""

import shutil
import time

TARGET = "voice_assistant.py"
MARKER = "DESTROY COMMAND FEATURE"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

if MARKER in src:
    print("Destroy command already present. Nothing to do.")
    raise SystemExit(0)

shutil.copy(TARGET, TARGET + f".bak.{int(time.time())}")

destroy_block = '''
# === DESTROY COMMAND FEATURE ===
import ctypes as _destroy_ctypes
import subprocess as _destroy_subprocess
import time as _destroy_time

_destroy_pending = {"armed": False, "armed_at": 0.0}
_DESTROY_CONFIRM_WINDOW_SECONDS = 15  # confirmation must follow within this window

# Window classes to leave alone -- these are shell/system chrome, not user apps.
_DESTROY_SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow", "TaskListThumbnailWnd",
}

def _destroy_close_all_windows():
    """Best-effort graceful close of visible top-level app windows, same as
    clicking the X on each -- unsaved-work prompts still appear. Does not
    force-kill anything."""
    user32 = _destroy_ctypes.windll.user32
    WM_CLOSE = 0x0010

    def enum_handler(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = _destroy_ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value in _DESTROY_SKIP_CLASSES:
            return True
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True

    EnumWindowsProc = _destroy_ctypes.WINFUNCTYPE(_destroy_ctypes.c_bool, _destroy_ctypes.c_int, _destroy_ctypes.c_int)
    user32.EnumWindows(EnumWindowsProc(enum_handler), 0)

def _destroy_execute():
    print("[Helix] Destroy confirmed. Closing open applications...")
    _destroy_close_all_windows()
    _destroy_time.sleep(5)  # give apps a moment to close / show save prompts
    print("[Helix] Shutting down.")
    # Plain (non-forced) shutdown: Windows will still prompt for anything that
    # didn't close cleanly above, rather than silently discarding work.
    _destroy_subprocess.run(["shutdown", "/s", "/t", "0"], capture_output=True)

def handle_destroy_command(text: str) -> bool:
    """Call this alongside your other command handlers, before sending text
    to the LLM. Returns True if the text was consumed by the destroy flow
    (armed or executed), False otherwise."""
    t = text.strip().lower()

    if _destroy_pending["armed"]:
        elapsed = _destroy_time.time() - _destroy_pending["armed_at"]
        if elapsed > _DESTROY_CONFIRM_WINDOW_SECONDS:
            _destroy_pending["armed"] = False  # window expired, fall through
        elif t in ("confirm destroy", "confirm"):
            _destroy_pending["armed"] = False
            _destroy_execute()
            return True
        else:
            _destroy_pending["armed"] = False  # anything else cancels it
            print("[Helix] Destroy cancelled.")
            return True

    if t == "destroy":
        _destroy_pending["armed"] = True
        _destroy_pending["armed_at"] = _destroy_time.time()
        print("[Helix] This will close all open applications and shut down the "
              "computer. Say 'confirm destroy' within 15 seconds to proceed, "
              "or anything else to cancel.")
        return True

    return False
# === END DESTROY COMMAND FEATURE ===
'''

src = src.rstrip() + "\n" + destroy_block

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print(f"Patched {TARGET}.")
print()
print("Add this near your other command checks (mute, close-app, etc.), before")
print("falling through to the LLM:")
print()
print("    if handle_destroy_command(user_text):")
print("        continue  # or return, depending on your loop structure")
print()
print("Flow once wired in:")
print('  You: "Destroy"')
print('  Helix: asks you to say "confirm destroy" within 15 seconds')
print('  You: "confirm destroy"  -> closes open apps, then shuts the PC down')
print('  You: anything else, or wait past 15s -> cancelled, nothing happens')

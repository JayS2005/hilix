"""
Run this on Windows (venv active) from C:\\jarvis-client:
    python patch_apps.py

Adds a local, whitelist-only app launcher to voice_assistant.py.
Say e.g. "Helix open chrome" / "Helix open vlc" / "Helix open obsidian".
Runs entirely on the Windows side - no round trip to the Kali agent for this.

NOTE: some paths guess common install locations; if one fails to launch,
tell me which app and I'll give you the exact path/command for your machine.
"""
import re

path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

APP_DICT = '''
# --- Whitelisted local app launcher (Windows side) ---
import subprocess as _subprocess

WINDOWS_APP_WHITELIST = {
    "utorrent": "utorrent",
    "brave": "brave",
    "cherrytree": "cherrytree",
    "packet tracer": "PacketTracer",
    "copilot": "msedge --app=https://copilot.microsoft.com",
    "cyberghost": "CyberGhost",
    "easeus": "EaseUS Data Recovery Wizard",
    "eset": "ESET Security",
    "chrome": "chrome",
    "google chrome": "chrome",
    "ip messenger": "ipmsg",
    "iperius remote": "IperiusRemote",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "onedrive": "onedrive",
    "onenote": "onenote",
    "vscode": "code",
    "visual studio code": "code",
    "geforce experience": "NVIDIA GeForce Experience",
    "obsidian": "obsidian",
    "peazip": "peazip",
    "proton vpn": "ProtonVPN",
    "push wallpaper": "PUSHVideoWallpaper",
    "remote desktop": "mstsc",
    "screenrec": "ScreenRec",
    "signal": "signal",
    "telegram": "Telegram",
    "terabox": "TeraBox",
    "ultraviewer": "UltraViewer",
    "vlc": "vlc",
    "vmware": "vmware",
    "voicemod": "voicemod",
    "windirstat": "windirstat",
    "wiztree": "wiztree",
    "xampp": "xampp-control",
    "zoho mail": "Zoho Mail",
    "zoom": "Zoom",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
}

def try_open_app(text_lower: str) -> bool:
    """If text names a whitelisted app, launch it and return True. Else return False."""
    for name, cmd in WINDOWS_APP_WHITELIST.items():
        if name in text_lower:
            try:
                _subprocess.Popen(cmd, shell=True)
                print(f"Launching: {name}")
            except Exception as e:
                print(f"Failed to launch {name}: {e}")
            return True
    return False
'''

if "WINDOWS_APP_WHITELIST" not in src:
    # insert after imports, before first def
    marker = "SAMPLE_RATE = 16000"
    assert marker in src, "insertion marker not found"
    src = src.replace(marker, marker + "\n" + APP_DICT)

    # hook into main loop: check for "open <app>" before hitting the agent
    old_loop = '''        if text:
            text = "Helix " + text
        print("You:", text)
        if not text:
            continue'''
    new_loop = '''        if text:
            text = "Helix " + text
        print("You:", text)
        if not text:
            continue
        if "open" in text.lower() and try_open_app(text.lower()):
            continue'''
    assert old_loop in src, "loop anchor not found"
    src = src.replace(old_loop, new_loop)

    open(path, "w", encoding="utf-8").write(src)
    print("patched successfully")
else:
    print("already patched, skipping")

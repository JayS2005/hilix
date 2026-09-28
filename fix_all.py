path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

changed = []

# 0. speed: fewer recording seconds, smaller default whisper model, faster piper/eleven timeout unaffected
old_rec_default = "def record(seconds=6):"
if old_rec_default in src:
    src = src.replace(old_rec_default, "def record(seconds=4):", 1)
    changed.append("recording length 6s -> 4s")

old_model_default = 'MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")'
if old_model_default in src:
    src = src.replace(old_model_default, 'MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")', 1)
    changed.append("whisper model small -> base (faster transcription)")

# 1. rename the printed status text
old_print = 'print(f"Recording {seconds}s...")'
if old_print in src:
    src = src.replace(old_print, 'print("Tuning...")', 1)
    changed.append('status text -> "Tuning..."')

# 2. add handle_os_command if missing
if "def handle_os_command" not in src:
    if "import re" not in src:
        src = src.replace("import difflib", "import difflib\nimport re", 1)

    anchor = "def try_open_app(text_lower: str) -> bool:"
    os_func = '''def handle_os_command(text_lower: str) -> bool:
    if "lock" in text_lower and ("screen" in text_lower or "computer" in text_lower or "workstation" in text_lower or text_lower.strip().endswith("lock")):
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        print("Locking workstation.")
        return True

    if "sleep" in text_lower and "and" not in text_lower:
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        print("Putting computer to sleep.")
        return True

    if "task scheduler" in text_lower:
        subprocess.Popen("taskschd.msc", shell=True)
        print("Opening Task Scheduler.")
        return True

    if "confirm shutdown" in text_lower:
        subprocess.Popen("shutdown /s /t 5", shell=True)
        print("Shutting down in 5 seconds. Run shutdown /a to cancel.")
        return True
    if "shutdown" in text_lower:
        print("Shutdown requires confirmation. Say: Helix confirm shutdown.")
        return True

    if "confirm restart" in text_lower:
        subprocess.Popen("shutdown /r /t 5", shell=True)
        print("Restarting in 5 seconds. Run shutdown /a to cancel.")
        return True
    if "restart" in text_lower:
        print("Restart requires confirmation. Say: Helix confirm restart.")
        return True

    if "confirm log off" in text_lower or "confirm logoff" in text_lower or "confirm sign out" in text_lower:
        subprocess.Popen("shutdown /l", shell=True)
        print("Logging off.")
        return True
    if "log off" in text_lower or "logoff" in text_lower or "sign out" in text_lower:
        print("Log off requires confirmation. Say: Helix confirm log off.")
        return True

    return False


'''
    assert anchor in src, "try_open_app anchor not found for os_command insert"
    src = src.replace(anchor, os_func + anchor, 1)
    changed.append("added handle_os_command (lock/sleep/shutdown/restart/logoff/task scheduler)")

# 3. add try_schedule_task if missing
if "def try_schedule_task" not in src:
    anchor2 = "def handle_os_command(text_lower: str) -> bool:"
    lines = [
        'SCHEDULED_ACTIONS = {',
        '    "antivirus scan": r\'"C:\\Program Files\\Windows Defender\\MpCmdRun.exe" -Scan -ScanType 1\',',
        '    "quick scan": r\'"C:\\Program Files\\Windows Defender\\MpCmdRun.exe" -Scan -ScanType 1\',',
        '    "full scan": r\'"C:\\Program Files\\Windows Defender\\MpCmdRun.exe" -Scan -ScanType 2\',',
        '}',
        '',
        'def _parse_time(text_lower):',
        '    m = re.search(r"\\b(\\d{1,2})(:(\\d{2}))?\\s*(am|pm)?\\b", text_lower)',
        '    if not m:',
        '        return None',
        '    hour = int(m.group(1))',
        '    minute = int(m.group(3)) if m.group(3) else 0',
        '    ampm = m.group(4)',
        '    if ampm == "pm" and hour != 12:',
        '        hour += 12',
        '    if ampm == "am" and hour == 12:',
        '        hour = 0',
        '    if hour > 23 or minute > 59:',
        '        return None',
        '    return "%02d:%02d" % (hour, minute)',
        '',
        'def try_schedule_task(text_lower):',
        '    if not ("wake" in text_lower or "get up" in text_lower or "sleep and" in text_lower or "schedule" in text_lower):',
        '        return False',
        '    if "run" not in text_lower:',
        '        return False',
        '',
        '    time_str = _parse_time(text_lower)',
        '    if not time_str:',
        '        print("Could not understand the time. Try: wake me at 2am and run antivirus scan")',
        '        return True',
        '',
        '    action_key = None',
        '    for key in SCHEDULED_ACTIONS:',
        '        if key in text_lower:',
        '            action_key = key',
        '            break',
        '    if not action_key:',
        '        print("Could not match a known scheduled action. Available: " + str(list(SCHEDULED_ACTIONS)))',
        '        return True',
        '',
        '    command = SCHEDULED_ACTIONS[action_key]',
        '    task_name = "Helix_" + action_key.replace(" ", "_")',
        '',
        '    ps_lines = [',
        '        \'$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument \\\'-WindowStyle Hidden -Command \\"\' + command + \'\\"\\\'\',',
        '        "$trigger = New-ScheduledTaskTrigger -Daily -At " + time_str,',
        '        "$settings = New-ScheduledTaskSettingsSet -WakeToRun",',
        '        \'Register-ScheduledTask -TaskName "\' + task_name + \'" -Action $action -Trigger $trigger -Settings $settings -Force\',',
        '    ]',
        '    ps_script = "; ".join(ps_lines)',
        '    try:',
        '        subprocess.run(["powershell.exe", "-Command", ps_script], check=True, capture_output=True, text=True)',
        '        print("Scheduled: wake at " + time_str + " daily and run " + action_key)',
        '    except subprocess.CalledProcessError as e:',
        '        print("Failed to schedule task: " + str(e.stderr))',
        '    return True',
        '',
        '',
    ]
    new_func = "\n".join(lines) + "\n" + anchor2
    assert anchor2 in src, "handle_os_command anchor not found for schedule insert"
    src = src.replace(anchor2, new_func, 1)
    changed.append("added try_schedule_task (voice-scheduled wake+scan)")

# 4. hook both into main loop, in order: schedule -> os_command -> open_app
old_hook = 'if "open" in text.lower() and try_open_app(text.lower()):\n            continue'
if old_hook in src and "try_schedule_task(text.lower())" not in src:
    new_hook = (
        'if try_schedule_task(text.lower()):\n'
        '            continue\n'
        '        if handle_os_command(text.lower()):\n'
        '            continue\n'
        '        ' + old_hook
    )
    src = src.replace(old_hook, new_hook, 1)
    changed.append("hooked schedule + os_command into main loop")

open(path, "w", encoding="utf-8").write(src)
print("DONE. Changes applied:")
for c in changed:
    print(" -", c)
if not changed:
    print(" (nothing new to apply, already up to date)")

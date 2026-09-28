path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "def try_schedule_task" in src:
    print("already present, skipping")
else:
    if "import re" not in src:
        src = src.replace("import difflib", "import difflib\nimport re", 1)

    anchor = "def handle_os_command(text_lower: str) -> bool:"

    new_func_lines = [
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
    new_func = "\n".join(new_func_lines) + "\n" + anchor

    assert anchor in src, "anchor not found"
    src = src.replace(anchor, new_func, 1)

    old_hook = 'if handle_os_command(text.lower()):\n            continue'
    new_hook = 'if try_schedule_task(text.lower()):\n            continue\n        if handle_os_command(text.lower()):\n            continue'
    assert old_hook in src, "hook anchor not found"
    src = src.replace(old_hook, new_hook, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

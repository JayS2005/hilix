path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "def launch_dashboard" in src:
    print("already present, skipping")
else:
    if "import webbrowser" not in src:
        src = src.replace("import os, io, subprocess, requests",
                           "import os, io, subprocess, requests\nimport webbrowser", 1)

    helper = '''
def launch_dashboard():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stats_script = os.path.join(base_dir, "stats_server.py")
    dashboard_html = os.path.join(base_dir, "helix_dashboard.html")

    if os.path.exists(stats_script):
        try:
            subprocess.Popen(
                ["python", stats_script],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=base_dir,
            )
            print("Stats server starting...")
        except Exception as e:
            print("Could not start stats server: " + str(e))
    else:
        print("stats_server.py not found next to voice_assistant.py, skipping.")

    if os.path.exists(dashboard_html):
        try:
            webbrowser.open("file:///" + dashboard_html.replace("\\\\", "/"))
            print("Opening dashboard...")
        except Exception as e:
            print("Could not open dashboard: " + str(e))
    else:
        print("helix_dashboard.html not found next to voice_assistant.py, skipping.")


'''
    anchor = 'if __name__ == "__main__":'
    assert anchor in src, "main anchor not found"
    src = src.replace(anchor, helper + anchor, 1)

    old_start = 'print("HELIX voice client. Ctrl+C to stop.")'
    new_start = 'print("HELIX voice client. Ctrl+C to stop.")\n    launch_dashboard()'
    assert old_start in src, "start print anchor not found"
    src = src.replace(old_start, new_start, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

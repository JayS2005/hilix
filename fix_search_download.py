path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "def search_web" in src:
    print("already present, skipping")
else:
    if "import subprocess" not in src:
        pass  # already imported at top in real file

    helper = '''
import os as _os_sd

HELIX_DOWNLOAD_DIR = _os_sd.path.join(_os_sd.path.expanduser("~"), "HelixDownloads")
_os_sd.makedirs(HELIX_DOWNLOAD_DIR, exist_ok=True)

_pending_search_results = []

def search_web(query):
    """Search via DuckDuckGo HTML endpoint (no API key needed). Returns list of (title, url)."""
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        print("Search failed: " + str(e))
        return []

    results = re.findall(r\'result__a" href="([^"]+)"[^>]*>(.*?)</a>\', r.text)
    cleaned = []
    for url, title in results[:3]:
        title_clean = re.sub("<[^>]+>", "", title)
        cleaned.append((title_clean, url))
    return cleaned


def download_and_scan(url, suggested_name):
    dest = _os_sd.path.join(HELIX_DOWNLOAD_DIR, suggested_name)
    try:
        r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "text/html" in content_type:
            print("That link points to a webpage, not a direct file. I will not save a webpage as if it were the tool.")
            print("Link for you to check manually: " + url)
            return
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > 50 * 1024 * 1024:
                    f.close()
                    _os_sd.remove(dest)
                    print("Download exceeded 50MB limit, aborted.")
                    return
                f.write(chunk)
        print("Downloaded to " + dest + ". Scanning with Windows Defender now...")
        scan_cmd = [
            r"C:\\Program Files\\Windows Defender\\MpCmdRun.exe",
            "-Scan", "-ScanType", "3", "-File", dest,
        ]
        try:
            result = subprocess.run(scan_cmd, capture_output=True, text=True, timeout=120)
            print("Scan result: " + result.stdout.strip()[-500:])
        except Exception as e:
            print("Could not run antivirus scan: " + str(e))
    except Exception as e:
        print("Download failed: " + str(e))


def try_search_or_select(text_lower):
    global _pending_search_results

    if _pending_search_results:
        if "cancel" in text_lower or "never mind" in text_lower:
            _pending_search_results = []
            print("Cancelled.")
            return True
        choice = None
        if "first" in text_lower or " one" in text_lower or "1" in text_lower:
            choice = 0
        elif "second" in text_lower or "two" in text_lower or "2" in text_lower:
            choice = 1
        elif "third" in text_lower or "three" in text_lower or "3" in text_lower:
            choice = 2
        if choice is not None and choice < len(_pending_search_results):
            title, url = _pending_search_results[choice]
            _pending_search_results = []
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", title)[:60] or "download"
            download_and_scan(url, safe_name)
            return True

    if "find" in text_lower or "search for" in text_lower or ("download" in text_lower and "http" not in text_lower):
        query = text_lower
        for trigger in ["helix", "find", "search for", "download"]:
            query = query.replace(trigger, "")
        query = query.strip()
        if not query:
            return False
        print("Searching for: " + query)
        results = search_web(query)
        if not results:
            print("No results found.")
            return True
        _pending_search_results = results
        for i, (title, url) in enumerate(results):
            print(str(i + 1) + ". " + title + " - " + url)
        print("Say 'first', 'second', 'third', or 'cancel'.")
        return True

    return False


'''
    anchor = "def handle_os_command(text_lower: str) -> bool:"
    assert anchor in src, "anchor not found"
    src = src.replace(anchor, helper + anchor, 1)

    old_hook = 'if handle_os_command(text.lower()):\n            continue'
    new_hook = 'if try_search_or_select(text.lower()):\n            continue\n        if handle_os_command(text.lower()):\n            continue'
    assert old_hook in src, "hook anchor not found"
    src = src.replace(old_hook, new_hook, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

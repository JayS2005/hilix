path = "voice_assistant.py"
src = open(path, encoding="utf-8").read()

if "MEDIA_KEYWORDS" in src:
    print("already present, skipping")
else:
    old = 'def try_search_or_select(text_lower):\n    global _pending_search_results'
    new = '''MEDIA_KEYWORDS = ["song", "music", "video", "mp3", "mp4", "movie", "album", "track", "lyrics"]

def try_search_or_select(text_lower):
    global _pending_search_results'''
    assert old in src, "anchor not found"
    src = src.replace(old, new, 1)

    old2 = '''        if choice is not None and choice < len(_pending_search_results):
            title, url = _pending_search_results[choice]
            _pending_search_results = []
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", title)[:60] or "download"
            download_and_scan(url, safe_name)
            return True'''
    new2 = '''        if choice is not None and choice < len(_pending_search_results):
            title, url = _pending_search_results[choice]
            is_media = any(k in title.lower() or k in url.lower() for k in MEDIA_KEYWORDS)
            _pending_search_results = []
            if is_media:
                print("That looks like a song/video link. I will not auto-download media - open it yourself here: " + url)
                return True
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", title)[:60] or "download"
            download_and_scan(url, safe_name)
            return True'''
    assert old2 in src, "download hook anchor not found"
    src = src.replace(old2, new2, 1)

    open(path, "w", encoding="utf-8").write(src)
    print("patched")

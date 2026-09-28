#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/jarvis-api"
source .venv/bin/activate

echo "== Writing app/tools/osint.py =="
cat > app/tools/osint.py << 'PYEOF'
import ipaddress
import shutil
import subprocess
from app.config import AUTHORIZED_NETWORKS


def _is_authorized_target(target: str) -> bool:
    try:
        ip = ipaddress.ip_address(target)
        return any(ip in net for net in AUTHORIZED_NETWORKS)
    except ValueError:
        return False


def whois_lookup(target: str) -> dict:
    if not _is_authorized_target(target):
        return {"ok": False, "error": "Target is outside AUTHORIZED_CIDRS."}
    binary = shutil.which("whois")
    if not binary:
        return {"ok": False, "error": "whois is not installed"}
    try:
        proc = subprocess.run([binary, target], capture_output=True, text=True, timeout=30, check=False)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout[-8000:], "stderr": proc.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "whois timed out"}


def dns_reverse_lookup(target: str) -> dict:
    if not _is_authorized_target(target):
        return {"ok": False, "error": "Target is outside AUTHORIZED_CIDRS."}
    binary = shutil.which("dig")
    if not binary:
        return {"ok": False, "error": "dig is not installed"}
    try:
        proc = subprocess.run([binary, "-x", target, "+short"], capture_output=True, text=True, timeout=15, check=False)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout.strip() or "No PTR record found", "stderr": proc.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "dig timed out"}


def http_headers(target: str, port: str = "80") -> dict:
    if not _is_authorized_target(target):
        return {"ok": False, "error": "Target is outside AUTHORIZED_CIDRS."}
    if not port.isdigit():
        return {"ok": False, "error": "Invalid port"}
    binary = shutil.which("curl")
    if not binary:
        return {"ok": False, "error": "curl is not installed"}
    url = "http://" + target + ":" + port
    try:
        proc = subprocess.run([binary, "-I", "--max-time", "10", url], capture_output=True, text=True, timeout=15, check=False)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "curl timed out"}
PYEOF
python3 -c "import ast; ast.parse(open('app/tools/osint.py').read())" && echo "osint.py syntax OK"

echo "== Patching app/openrouter.py (tool schemas) =="
python3 - << 'EOF'
path = "app/openrouter.py"
src = open(path).read()

if '"whois_lookup"' in src:
    print("tool schemas already present, skipping")
else:
    anchor = "TOOLS = ["
    new_tools = '''TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "whois_lookup",
            "description": "Run a WHOIS lookup against an authorized lab IP address.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "IPv4 address in the authorized lab network"}},
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dns_reverse_lookup",
            "description": "Run a reverse DNS (PTR) lookup against an authorized lab IP address.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "IPv4 address in the authorized lab network"}},
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_headers",
            "description": "Fetch HTTP response headers from an authorized lab IP address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "IPv4 address in the authorized lab network"},
                    "port": {"type": "string", "description": "Port number, default 80"}
                },
                "required": ["target"]
            }
        }
    },
'''
    assert anchor in src, "TOOLS anchor not found"
    src = src.replace(anchor, new_tools, 1)
    open(path, "w").write(src)
    print("openrouter.py patched")
EOF

echo "== Patching app/main.py (dispatch) =="
python3 - << 'EOF'
path = "app/main.py"
src = open(path).read()

if "from app.tools.osint import" not in src:
    src = src.replace(
        "from app.tools.basic import run_local_info",
        "from app.tools.basic import run_local_info\nfrom app.tools.osint import whois_lookup, dns_reverse_lookup, http_headers"
    )

old = '''            elif name == "local_tool_info":
                result = run_local_info()
            else:'''
new = '''            elif name == "local_tool_info":
                result = run_local_info()
            elif name == "whois_lookup":
                result = whois_lookup(args["target"])
            elif name == "dns_reverse_lookup":
                result = dns_reverse_lookup(args["target"])
            elif name == "http_headers":
                result = http_headers(args["target"], args.get("port", "80"))
            else:'''
assert old in src, "dispatch anchor not found"
src = src.replace(old, new)
open(path, "w").write(src)
print("main.py patched")
EOF

python3 -c "import ast; ast.parse(open('app/openrouter.py').read()); ast.parse(open('app/main.py').read())" && echo "ALL FILES VALID"

echo ""
echo "== DONE =="

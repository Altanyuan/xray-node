#!/usr/bin/env python3
"""Render runtime wrapper (route A): download xray-core at boot, generate
config from env, run VLESS+WS. Stdlib only.
Listens on 0.0.0.0:$PORT (platform-provided). TLS is terminated by the
platform edge, so the local inbound is plain WS.
Env: PORT (platform), UUID (node uuid), WS_PATH (default /vless).
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile

XRAY_URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
WORKDIR = os.path.dirname(os.path.abspath(__file__))


def log(*a):
    print("[wrapper]", *a, flush=True)


def ensure_xray():
    exe = os.path.join(WORKDIR, "xray")
    if os.path.isfile(exe) and os.access(exe, os.X_OK):
        log("xray binary present")
        return exe
    zpath = os.path.join(WORKDIR, "xray.zip")
    log("downloading xray-core ...")
    req = urllib.request.Request(XRAY_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(zpath, "wb") as f:
        shutil.copyfileobj(r, f)
    with zipfile.ZipFile(zpath) as z:
        z.extract("xray", WORKDIR)
    os.chmod(exe, 0o755)
    os.remove(zpath)
    log("xray downloaded")
    return exe


def main():
    port = int(os.environ.get("PORT", "8080"))
    node_uuid = os.environ.get("UUID") or str(uuid.uuid4())
    ws_path = os.environ.get("WS_PATH", "/vless")
    if not ws_path.startswith("/"):
        ws_path = "/" + ws_path
    exe = ensure_xray()
    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": port,
            "listen": "0.0.0.0",
            "protocol": "vless",
            "settings": {"clients": [{"id": node_uuid}], "decryption": "none"},
            "streamSettings": {"network": "ws", "wsSettings": {"path": ws_path}},
        }],
        "outbounds": [{"protocol": "freedom"}],
    }
    cfg_path = os.path.join(WORKDIR, "config.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)
    log("listening on 0.0.0.0:%d path=%s uuid=%s" % (port, ws_path, node_uuid))
    proc = subprocess.Popen([exe, "run", "-c", cfg_path])
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    main()

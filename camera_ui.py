#!/usr/bin/env python3
"""
camera-streamer Web UI
A browser-based control panel for the camera-streamer service on OctoPi (64-bit)
with Raspberry Pi Camera Module 3 (IMX708).

Run on the Pi:  python3 /home/pi/camera-streamer-ui/camera_ui.py
Access at:      http://<your-pi-ip>:5001

GitHub: https://github.com/D4n13l000/camera-streamer-ui
License: MIT
"""

import subprocess
import re
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

CONFIG_PATH = "/etc/camera-streamer.conf.d/libcamera.conf"
CAMERA_API  = "http://localhost:8080"

# IMX708 (Raspberry Pi Camera Module 3) native sensor resolution
# Used for ScalerCrop (digital zoom) coordinate calculation
SENSOR_W = 4608
SENSOR_H = 2592

# ── Config IO ─────────────────────────────────────────────────────────────────

def read_config():
    try:
        with open(CONFIG_PATH) as f:
            return f.read()
    except Exception:
        return ""

def parse_config(text):
    p = {
        "PORT": 8080, "WIDTH": 1920, "HEIGHT": 1080,
        "VIDEO_HEIGHT": 1080, "SNAPSHOT_HEIGHT": 2592,
        "FRAMERATE": 15, "CAMERA_OPTIONS": {},
        "SNAPSHOT_QUALITY": 96, "STREAM_QUALITY": 75,
    }
    for k in ["PORT", "WIDTH", "HEIGHT", "VIDEO_HEIGHT", "SNAPSHOT_HEIGHT", "FRAMERATE"]:
        m = re.search(rf"^{k}=(.+)$", text, re.MULTILINE)
        if m:
            try:    p[k] = int(m.group(1).strip())
            except: p[k] = m.group(1).strip()
    for m in re.finditer(r'--camera-options="([^=]+)=([^"]*)"', text):
        p["CAMERA_OPTIONS"][m.group(1)] = m.group(2)
    m = re.search(r'--camera-snapshot\.options="quality=([^"]*)"', text)
    if m: p["SNAPSHOT_QUALITY"] = int(m.group(1))
    m = re.search(r'--camera-stream\.options="quality=([^"]*)"', text)
    if m: p["STREAM_QUALITY"] = int(m.group(1))
    return p

def build_config(p):
    lines = [f"{k}={p[k]}" for k in ["PORT","WIDTH","HEIGHT","VIDEO_HEIGHT","SNAPSHOT_HEIGHT","FRAMERATE"]]
    opts  = ["--http-listen=0.0.0.0"]
    for k, v in p["CAMERA_OPTIONS"].items():
        opts.append(f'--camera-options="{k}={v}"')
    opts.append(f'--camera-snapshot.options="quality={p["SNAPSHOT_QUALITY"]}"')
    opts.append(f'--camera-stream.options="quality={p["STREAM_QUALITY"]}"')
    lines.append(f"OPTIONS='{' '.join(opts)}'")
    return "\n".join(lines) + "\n"

def write_config(p):
    tmp = "/tmp/camera-ui.conf"
    with open(tmp, "w") as f:
        f.write(build_config(p))
    subprocess.run(["sudo", "cp", tmp, CONFIG_PATH], check=True)
    subprocess.run(["sudo", "rm", tmp])

# ── camera-streamer HTTP API ──────────────────────────────────────────────────

def api_set(device, key, value):
    try:
        r = requests.post(
            f"{CAMERA_API}/option",
            params={"device": device, "key": key, "value": value},
            timeout=3,
        )
        return r.status_code == 200
    except Exception:
        return False

# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/config")
def get_config():
    c = parse_config(read_config())
    c["SENSOR_W"] = SENSOR_W
    c["SENSOR_H"] = SENSOR_H
    return jsonify(c)

@app.route("/api/camera_option", methods=["POST"])
def set_camera_option():
    d  = request.json
    ok = api_set("CAMERA", d["key"], d["value"])
    if d.get("save", True):
        c = parse_config(read_config())
        c["CAMERA_OPTIONS"][d["key"]] = str(d["value"])
        write_config(c)
    return jsonify({"ok": ok})

@app.route("/api/stream_quality", methods=["POST"])
def set_stream_quality():
    v = request.json["value"]
    api_set("STREAM", "quality", v)
    c = parse_config(read_config())
    c["STREAM_QUALITY"] = int(v)
    write_config(c)
    return jsonify({"ok": True})

@app.route("/api/snapshot_quality", methods=["POST"])
def set_snapshot_quality():
    v = request.json["value"]
    api_set("SNAPSHOT", "quality", v)
    c = parse_config(read_config())
    c["SNAPSHOT_QUALITY"] = int(v)
    write_config(c)
    return jsonify({"ok": True})

@app.route("/api/stream_config", methods=["POST"])
def set_stream_config():
    d = request.json
    c = parse_config(read_config())
    for k in ["WIDTH", "HEIGHT", "FRAMERATE"]:
        if k in d:
            c[k] = d[k]
    write_config(c)
    return jsonify({"ok": True})

@app.route("/api/restart", methods=["POST"])
def restart_camera():
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "camera-streamer-libcamera"],
            check=True,
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/restart_pi", methods=["POST"])
def restart_pi():
    subprocess.Popen(["sudo", "reboot"])
    return jsonify({"ok": True})

@app.route("/api/service_status")
def service_status():
    r = subprocess.run(
        ["systemctl", "is-active", "camera-streamer-libcamera"],
        capture_output=True, text=True,
    )
    return jsonify({"status": r.stdout.strip()})

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Camera Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#0d0f11; --surface:#141618; --border:#232629; --border2:#2e3338;
  --text:#c8cdd4; --muted:#565c66; --accent:#e8a020; --accent2:#1a9e6e;
  --danger:#c0392b; --info:#2980b9;
  --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
}
*, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font-family:var(--sans); font-size:14px; min-height:100vh; }

header {
  background:var(--surface); border-bottom:1px solid var(--border);
  padding:0 20px; height:52px; display:flex; align-items:center; gap:14px;
  position:sticky; top:0; z-index:200;
}
.logo { font-family:var(--mono); font-size:13px; font-weight:600; letter-spacing:.08em; color:var(--accent); text-transform:uppercase; }
.logo span { color:var(--muted); font-weight:400; }
.status-pill { margin-left:auto; display:flex; align-items:center; gap:7px; font-family:var(--mono); font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
.dot { width:7px; height:7px; border-radius:50%; background:var(--muted); transition:background .4s; }
.dot.active { background:var(--accent2); box-shadow:0 0 6px var(--accent2); }
.dot.error  { background:var(--danger); }

.layout { display:flex; min-height:calc(100vh - 52px); }
.main-wrap { flex:1 1 0; min-width:0; overflow-y:auto; }

aside {
  background:var(--surface); border-right:1px solid var(--border);
  padding:16px 0; position:sticky; top:52px;
  height:calc(100vh - 52px); overflow-y:auto; flex-shrink:0; width:200px;
}
.nav-section { padding:5px 14px 3px; font-family:var(--mono); font-size:10px; letter-spacing:.1em; color:var(--muted); text-transform:uppercase; }
.nav-item { display:flex; align-items:center; gap:8px; padding:8px 18px; cursor:pointer; color:var(--muted); font-size:13px; transition:color .15s,background .15s; border-left:2px solid transparent; user-select:none; }
.nav-item:hover { color:var(--text); background:rgba(255,255,255,.03); }
.nav-item.active { color:var(--accent); border-left-color:var(--accent); background:rgba(232,160,32,.05); }
.nav-item svg { flex-shrink:0; opacity:.7; }
.nav-item.active svg { opacity:1; }

main { padding:24px 28px; }

.resizer {
  width:5px; cursor:col-resize; background:var(--border); flex-shrink:0;
  transition:background .15s; position:relative;
}
.resizer:hover, .resizer.dragging { background:var(--accent); }
.resizer::after {
  content:''; position:absolute; top:50%; left:50%;
  transform:translate(-50%,-50%);
  width:1px; height:32px; background:currentColor; opacity:.3;
}

.cam-panel {
  background:var(--surface); padding:14px;
  position:sticky; top:52px; height:calc(100vh - 52px); overflow-y:auto;
  display:flex; flex-direction:column; gap:12px;
  flex-shrink:0; width:400px; min-width:200px; max-width:70vw;
}
.cam-panel.hidden { display:none; }
.cam-section-title { font-family:var(--mono); font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin-bottom:6px; }
.cam-feed { background:#000; border:1px solid var(--border); border-radius:5px; overflow:hidden; position:relative; cursor:zoom-in; }
.cam-feed img { width:100%; display:block; aspect-ratio:16/9; object-fit:cover; background:#000; transition:opacity .15s; }
.cam-feed:hover img { opacity:.88; }
.cam-badge { position:absolute; top:6px; left:6px; background:rgba(0,0,0,.65); color:var(--accent); font-family:var(--mono); font-size:9px; letter-spacing:.06em; text-transform:uppercase; padding:2px 7px; border-radius:3px; }
.snap-timer { font-family:var(--mono); font-size:10px; color:var(--muted); text-align:right; margin-top:4px; }

#fsOverlay { display:none; position:fixed; inset:0; z-index:1000; background:rgba(0,0,0,.92); cursor:zoom-out; align-items:center; justify-content:center; }
#fsOverlay.show { display:flex; }
#fsOverlay img { max-width:96vw; max-height:96vh; object-fit:contain; border-radius:4px; border:1px solid var(--border2); }
#fsBadge { position:fixed; top:16px; left:50%; transform:translateX(-50%); background:rgba(0,0,0,.7); color:var(--accent); font-family:var(--mono); font-size:11px; letter-spacing:.08em; padding:4px 14px; border-radius:4px; text-transform:uppercase; pointer-events:none; }
#fsClose { position:fixed; top:14px; right:20px; background:transparent; border:1px solid var(--border2); color:var(--muted); font-family:var(--mono); font-size:18px; width:34px; height:34px; border-radius:4px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all .15s; }
#fsClose:hover { border-color:var(--accent); color:var(--accent); }

.panel { display:none; }
.panel.active { display:block; }
.panel-title { font-family:var(--mono); font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin-bottom:18px; padding-bottom:8px; border-bottom:1px solid var(--border); }

.card { background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:18px 20px; margin-bottom:14px; }
.card-title { font-family:var(--mono); font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); margin-bottom:16px; }

.control-row { display:grid; grid-template-columns:180px 260px 72px; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid var(--border); }
.control-row:last-child { border-bottom:none; }
.ctrl-label { font-family:var(--mono); font-size:12px; color:var(--text); }
.ctrl-sub { font-size:10px; color:var(--muted); margin-top:2px; }

input[type=range] { -webkit-appearance:none; width:100%; height:3px; background:var(--border2); border-radius:2px; outline:none; cursor:pointer; }
input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:14px; height:14px; border-radius:50%; background:var(--accent); cursor:pointer; transition:transform .1s; }
input[type=range]::-webkit-slider-thumb:hover { transform:scale(1.2); }
input[type=range]::-moz-range-thumb { width:14px; height:14px; border-radius:50%; background:var(--accent); border:none; cursor:pointer; }
.val-display { font-family:var(--mono); font-size:12px; color:var(--accent); text-align:right; }

select { background:var(--bg); border:1px solid var(--border2); color:var(--text); font-family:var(--mono); font-size:12px; padding:6px 28px 6px 10px; border-radius:4px; width:100%; cursor:pointer; outline:none; appearance:none; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23565c66'/%3E%3C/svg%3E"); background-repeat:no-repeat; background-position:right 10px center; }
select:focus { border-color:var(--accent); }

.toggle-wrap { display:flex; align-items:center; gap:10px; }
.toggle { position:relative; width:38px; height:20px; }
.toggle input { opacity:0; width:0; height:0; }
.toggle-track { position:absolute; inset:0; background:var(--border2); border-radius:10px; cursor:pointer; transition:background .2s; }
.toggle input:checked + .toggle-track { background:var(--accent2); }
.toggle-thumb { position:absolute; top:3px; left:3px; width:14px; height:14px; background:#fff; border-radius:50%; transition:transform .2s; pointer-events:none; }
.toggle input:checked ~ .toggle-thumb { transform:translateX(18px); }

.btn { display:inline-flex; align-items:center; gap:7px; padding:7px 14px; border-radius:4px; border:1px solid var(--border2); background:transparent; color:var(--text); font-family:var(--mono); font-size:12px; cursor:pointer; transition:all .15s; text-transform:uppercase; letter-spacing:.06em; }
.btn:hover { border-color:var(--accent); color:var(--accent); }
.btn.primary { background:var(--accent); border-color:var(--accent); color:#000; font-weight:600; }
.btn.primary:hover { opacity:.85; color:#000; }
.btn.danger { border-color:var(--danger); color:var(--danger); }
.btn.danger:hover { background:var(--danger); color:#fff; }
.btn.info { border-color:var(--info); color:var(--info); }
.btn.info:hover { background:var(--info); color:#fff; }
.btn-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }

.zoom-display { font-family:var(--mono); font-size:26px; font-weight:600; color:var(--accent); text-align:center; padding:8px 0 2px; }
.zoom-sub { font-family:var(--mono); font-size:10px; color:var(--muted); text-align:center; margin-bottom:12px; }

.preset-grid { display:flex; gap:7px; flex-wrap:wrap; }
.preset-btn { padding:5px 12px; border:1px solid var(--border2); border-radius:4px; background:transparent; color:var(--muted); font-family:var(--mono); font-size:11px; cursor:pointer; transition:all .15s; }
.preset-btn:hover, .preset-btn.sel { border-color:var(--accent); color:var(--accent); background:rgba(232,160,32,.06); }
.ctrl-wide { grid-column:2/4; }

.info-box { background:rgba(41,128,185,.08); border:1px solid rgba(41,128,185,.25); border-radius:5px; padding:9px 13px; font-size:12px; color:#7fb3d3; margin-bottom:12px; line-height:1.6; }

#toast { position:fixed; bottom:20px; right:20px; background:var(--surface); border:1px solid var(--border2); border-left:3px solid var(--accent2); padding:11px 16px; border-radius:6px; font-family:var(--mono); font-size:12px; color:var(--text); opacity:0; transform:translateY(8px); transition:opacity .25s,transform .25s; pointer-events:none; z-index:999; max-width:280px; }
#toast.show { opacity:1; transform:translateY(0); }
#toast.err  { border-left-color:var(--danger); }
</style>
</head>
<body>

<header>
  <div class="logo">Camera<span>/</span>Control</div>
  <div style="font-size:11px;color:var(--muted);font-family:var(--mono);">camera-streamer UI · port 5001</div>
  <div class="status-pill">
    <div class="dot" id="statusDot"></div>
    <span id="statusText">—</span>
  </div>
</header>

<div class="layout">

<aside>
  <div class="nav-section">Image</div>
  <div class="nav-item active" data-panel="exposure" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
    Exposure
  </div>
  <div class="nav-item" data-panel="wb" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 2a7 7 0 1 0 0 14A7 7 0 0 0 12 2z"/><path d="M12 16v6M8 18h8"/></svg>
    White Balance
  </div>
  <div class="nav-item" data-panel="image" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="m3 15 5-5 4 4 3-3 6 6"/></svg>
    Color &amp; Detail
  </div>
  <div class="nav-item" data-panel="focus" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M3 9V5h4M21 9V5h-4M3 15v4h4M21 15v4h-4"/></svg>
    Focus (AF)
  </div>
  <div class="nav-item" data-panel="zoom" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35M11 8v6M8 11h6"/></svg>
    Digital Zoom
  </div>
  <div class="nav-section" style="margin-top:10px;">Stream</div>
  <div class="nav-item" data-panel="stream" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/></svg>
    Resolution &amp; Quality
  </div>
  <div class="nav-section" style="margin-top:10px;">System</div>
  <div class="nav-item" data-panel="system" onclick="nav(this)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
    System
  </div>
</aside>

<div class="main-wrap">
<main>

<!-- EXPOSURE -->
<div class="panel active" id="panel-exposure">
  <div class="panel-title">Exposure</div>
  <div class="card">
    <div class="card-title">Auto Exposure (AE)</div>
    <div class="control-row">
      <div><div class="ctrl-label">AE enabled</div><div class="ctrl-sub">AeEnable</div></div>
      <div class="toggle-wrap"><label class="toggle"><input type="checkbox" id="tog-AeEnable" checked onchange="sendToggle('AeEnable',this.checked)"><div class="toggle-track"></div><div class="toggle-thumb"></div></label></div>
      <div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AE lock</div><div class="ctrl-sub">AeLock — freeze current exposure</div></div>
      <div class="toggle-wrap"><label class="toggle"><input type="checkbox" id="tog-AeLock" onchange="sendToggle('AeLock',this.checked?1:0)"><div class="toggle-track"></div><div class="toggle-thumb"></div></label></div>
      <div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Metering mode</div><div class="ctrl-sub">AeMeteringMode</div></div>
      <select id="sel-AeMeteringMode" onchange="sendSelect('AeMeteringMode',this.value)">
        <option value="0">0 — CentreWeighted</option>
        <option value="1">1 — Spot</option>
        <option value="2">2 — Matrix</option>
        <option value="3">3 — Custom</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Exposure mode</div><div class="ctrl-sub">AeExposureMode</div></div>
      <select id="sel-AeExposureMode" onchange="sendSelect('AeExposureMode',this.value)">
        <option value="0">0 — Normal</option>
        <option value="1">1 — Short</option>
        <option value="2">2 — Long</option>
        <option value="3">3 — Custom</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Constraint mode</div><div class="ctrl-sub">AeConstraintMode</div></div>
      <select id="sel-AeConstraintMode" onchange="sendSelect('AeConstraintMode',this.value)">
        <option value="0">0 — Normal</option>
        <option value="1">1 — Highlight</option>
        <option value="2">2 — Shadows</option>
        <option value="3">3 — Custom</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">EV compensation</div><div class="ctrl-sub">ExposureValue  −8 … +8 EV</div></div>
      <input type="range" id="sl-ExposureValue" min="-8" max="8" step="0.1" value="0" oninput="upd('ExposureValue',this.value)" onchange="sendSlider('ExposureValue',this.value)">
      <div class="val-display" id="val-ExposureValue">0.0</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Manual Exposure</div>
    <div class="info-box">Effective when AE is disabled. ExposureTime = 0 → auto.</div>
    <div class="control-row">
      <div><div class="ctrl-label">Shutter speed</div><div class="ctrl-sub">ExposureTime  µs  (0 = auto)</div></div>
      <input type="range" id="sl-ExposureTime" min="0" max="200000" step="100" value="0" oninput="upd('ExposureTime',this.value)" onchange="sendSlider('ExposureTime',this.value)">
      <div class="val-display" id="val-ExposureTime">auto</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Analogue gain</div><div class="ctrl-sub">AnalogueGain  1.0 … 16.0</div></div>
      <input type="range" id="sl-AnalogueGain" min="1.0" max="16.0" step="0.1" value="1.0" oninput="upd('AnalogueGain',this.value)" onchange="sendSlider('AnalogueGain',this.value)">
      <div class="val-display" id="val-AnalogueGain">1.0</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Digital gain</div><div class="ctrl-sub">DigitalGain  1.0 … 8.0</div></div>
      <input type="range" id="sl-DigitalGain" min="1.0" max="8.0" step="0.1" value="1.0" oninput="upd('DigitalGain',this.value)" onchange="sendSlider('DigitalGain',this.value)">
      <div class="val-display" id="val-DigitalGain">1.0</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">HDR &amp; Frame Duration</div>
    <div class="control-row">
      <div><div class="ctrl-label">HDR mode</div><div class="ctrl-sub">HdrMode</div></div>
      <select id="sel-HdrMode" onchange="sendSelect('HdrMode',this.value)">
        <option value="0">0 — Off</option>
        <option value="1">1 — MultiExposureUnmerged</option>
        <option value="2">2 — MultiExposure</option>
        <option value="3">3 — SingleExposure</option>
        <option value="4">4 — Night</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Frame duration</div><div class="ctrl-sub">FrameDurationLimits</div></div>
      <select id="sel-FrameDurationLimits" onchange="sendSelect('FrameDurationLimits',this.value)">
        <option value="0,999999">Auto (unlimited)</option>
        <option value="66667,66667">15 fps fixed</option>
        <option value="33333,33333">30 fps fixed</option>
        <option value="16667,16667">60 fps fixed</option>
      </select><div></div>
    </div>
  </div>
</div>

<!-- WHITE BALANCE -->
<div class="panel" id="panel-wb">
  <div class="panel-title">White Balance</div>
  <div class="card">
    <div class="card-title">Auto White Balance (AWB)</div>
    <div class="control-row">
      <div><div class="ctrl-label">AWB enabled</div><div class="ctrl-sub">AwbEnable</div></div>
      <div class="toggle-wrap"><label class="toggle"><input type="checkbox" id="tog-AwbEnable" checked onchange="sendToggle('AwbEnable',this.checked)"><div class="toggle-track"></div><div class="toggle-thumb"></div></label></div>
      <div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AWB lock</div><div class="ctrl-sub">AwbLock — freeze current WB</div></div>
      <div class="toggle-wrap"><label class="toggle"><input type="checkbox" id="tog-AwbLock" onchange="sendToggle('AwbLock',this.checked?1:0)"><div class="toggle-track"></div><div class="toggle-thumb"></div></label></div>
      <div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AWB mode</div><div class="ctrl-sub">AwbMode</div></div>
      <select id="sel-AwbMode" onchange="sendSelect('AwbMode',this.value)">
        <option value="0">0 — Auto</option>
        <option value="1">1 — Incandescent (~2800K)</option>
        <option value="2">2 — Tungsten (~3200K)</option>
        <option value="3">3 — Fluorescent (~4000K)</option>
        <option value="4">4 — Indoor</option>
        <option value="5">5 — Daylight (~5500K)</option>
        <option value="6">6 — Cloudy (~6500K)</option>
      </select><div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Manual White Balance</div>
    <div class="control-row">
      <div><div class="ctrl-label">Colour temperature</div><div class="ctrl-sub">ColourTemperature  2000…10000 K</div></div>
      <input type="range" id="sl-ColourTemperature" min="2000" max="10000" step="100" value="5600" oninput="upd('ColourTemperature',this.value)" onchange="sendSlider('ColourTemperature',this.value)">
      <div class="val-display" id="val-ColourTemperature">5600K</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Red gain</div><div class="ctrl-sub">ColourGains.red  0…32</div></div>
      <input type="range" id="sl-ColourGainsR" min="0" max="32" step="0.05" value="1.0" oninput="upd('ColourGainsR',this.value)" onchange="sendColourGains()">
      <div class="val-display" id="val-ColourGainsR">1.0</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Blue gain</div><div class="ctrl-sub">ColourGains.blue  0…32</div></div>
      <input type="range" id="sl-ColourGainsB" min="0" max="32" step="0.05" value="1.0" oninput="upd('ColourGainsB',this.value)" onchange="sendColourGains()">
      <div class="val-display" id="val-ColourGainsB">1.0</div>
    </div>
  </div>
</div>

<!-- COLOR & DETAIL -->
<div class="panel" id="panel-image">
  <div class="panel-title">Color &amp; Detail</div>
  <div class="card">
    <div class="card-title">Image adjustments</div>
    <div class="control-row">
      <div><div class="ctrl-label">Brightness</div><div class="ctrl-sub">Brightness  −1…+1</div></div>
      <input type="range" id="sl-Brightness" min="-1" max="1" step="0.01" value="0" oninput="upd('Brightness',this.value)" onchange="sendSlider('Brightness',this.value)">
      <div class="val-display" id="val-Brightness">0.00</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Contrast</div><div class="ctrl-sub">Contrast  0…32</div></div>
      <input type="range" id="sl-Contrast" min="0" max="32" step="0.1" value="1.0" oninput="upd('Contrast',this.value)" onchange="sendSlider('Contrast',this.value)">
      <div class="val-display" id="val-Contrast">1.0</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Saturation</div><div class="ctrl-sub">Saturation  0…32  (0 = greyscale)</div></div>
      <input type="range" id="sl-Saturation" min="0" max="32" step="0.1" value="1.0" oninput="upd('Saturation',this.value)" onchange="sendSlider('Saturation',this.value)">
      <div class="val-display" id="val-Saturation">1.0</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Sharpness</div><div class="ctrl-sub">Sharpness  0…16</div></div>
      <input type="range" id="sl-Sharpness" min="0" max="16" step="0.1" value="1.0" oninput="upd('Sharpness',this.value)" onchange="sendSlider('Sharpness',this.value)">
      <div class="val-display" id="val-Sharpness">1.0</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Processing</div>
    <div class="control-row">
      <div><div class="ctrl-label">Noise reduction</div><div class="ctrl-sub">NoiseReductionMode</div></div>
      <select id="sel-NoiseReductionMode" onchange="sendSelect('NoiseReductionMode',this.value)">
        <option value="0">0 — Off</option>
        <option value="1">1 — Fast</option>
        <option value="2">2 — HighQuality</option>
      </select><div></div>
    </div>
  </div>
</div>

<!-- FOCUS -->
<div class="panel" id="panel-focus">
  <div class="panel-title">Focus (AF)</div>
  <div class="card">
    <div class="card-title">AF mode &amp; behaviour</div>
    <div class="control-row">
      <div><div class="ctrl-label">AF mode</div><div class="ctrl-sub">AfMode</div></div>
      <select id="sel-AfMode" onchange="sendSelect('AfMode',this.value);afModeChanged(this.value)">
        <option value="0">0 — Manual</option>
        <option value="1">1 — Auto (single, needs trigger)</option>
        <option value="2">2 — Continuous</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AF range</div><div class="ctrl-sub">AfRange</div></div>
      <select id="sel-AfRange" onchange="sendSelect('AfRange',this.value)">
        <option value="0">0 — Normal</option>
        <option value="1">1 — Macro</option>
        <option value="2">2 — Full</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AF speed</div><div class="ctrl-sub">AfSpeed</div></div>
      <select id="sel-AfSpeed" onchange="sendSelect('AfSpeed',this.value)">
        <option value="0">0 — Normal</option>
        <option value="1">1 — Fast</option>
      </select><div></div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">AF metering</div><div class="ctrl-sub">AfMetering</div></div>
      <select id="sel-AfMetering" onchange="sendSelect('AfMetering',this.value)">
        <option value="0">0 — Auto</option>
        <option value="1">1 — Windows</option>
      </select><div></div>
    </div>
    <div class="control-row" id="row-AfTrigger">
      <div><div class="ctrl-label">AF trigger</div><div class="ctrl-sub">AfTrigger — Auto mode only</div></div>
      <div style="display:flex;gap:8px;">
        <button class="btn info" onclick="sendSelect('AfTrigger',0)">▶ Start focus</button>
        <button class="btn" onclick="sendSelect('AfTrigger',1)">✕ Cancel</button>
      </div><div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Manual focus</div>
    <div class="info-box">Active when AfMode = Manual. 0.0 = infinity, ~35 = macro.</div>
    <div class="control-row">
      <div><div class="ctrl-label">Lens position</div><div class="ctrl-sub">LensPosition  0.0…35.0</div></div>
      <input type="range" id="sl-LensPosition" min="0" max="35" step="0.1" value="0" oninput="upd('LensPosition',this.value)" onchange="sendSlider('LensPosition',this.value)">
      <div class="val-display" id="val-LensPosition">0.0</div>
    </div>
  </div>
</div>

<!-- DIGITAL ZOOM -->
<div class="panel" id="panel-zoom">
  <div class="panel-title">Digital Zoom</div>
  <div class="card">
    <div class="card-title">ScalerCrop — sensor crop</div>
    <div class="info-box">Digital zoom crops a region from the full sensor image (ScalerCrop) and scales it to the stream resolution. IMX708 full sensor: <strong>4608 × 2592 px</strong>. Higher stream resolution = sharper zoom.</div>
    <div class="zoom-display" id="zoom-label">1.0×</div>
    <div class="zoom-sub" id="zoom-crop-info">ScalerCrop: 0,0,4608,2592</div>
    <div style="padding:6px 0 14px;">
      <input type="range" id="sl-zoom" min="1" max="8" step="0.1" value="1" oninput="zoomChanged(this.value)" style="width:100%;max-width:260px;">
    </div>
    <div class="control-row" style="border:none;padding-top:0;">
      <div><div class="ctrl-label">Presets</div></div>
      <div class="preset-grid ctrl-wide">
        <button class="preset-btn sel" onclick="setZoom(1,this)">1×</button>
        <button class="preset-btn" onclick="setZoom(1.5,this)">1.5×</button>
        <button class="preset-btn" onclick="setZoom(2,this)">2×</button>
        <button class="preset-btn" onclick="setZoom(3,this)">3×</button>
        <button class="preset-btn" onclick="setZoom(4,this)">4×</button>
        <button class="preset-btn" onclick="setZoom(6,this)">6×</button>
        <button class="preset-btn" onclick="setZoom(8,this)">8×</button>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn primary" onclick="applyZoom()">⟳ Apply zoom</button>
      <button class="btn" onclick="setZoom(1,null);applyZoom()">↺ Reset to 1×</button>
    </div>
  </div>
</div>

<!-- RESOLUTION & QUALITY -->
<div class="panel" id="panel-stream">
  <div class="panel-title">Resolution &amp; Quality</div>
  <div class="card">
    <div class="card-title">Resolution (requires restart)</div>
    <div class="control-row">
      <div><div class="ctrl-label">Preset</div><div class="ctrl-sub">WIDTH × HEIGHT</div></div>
      <div class="preset-grid ctrl-wide" id="res-btns">
        <button class="preset-btn" onclick="setRes(1280,720,this)">1280×720</button>
        <button class="preset-btn sel" onclick="setRes(1920,1080,this)">1920×1080</button>
        <button class="preset-btn" onclick="setRes(2304,1296,this)">2304×1296</button>
        <button class="preset-btn" onclick="setRes(4608,2592,this)">4608×2592</button>
      </div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Frame rate</div><div class="ctrl-sub">FRAMERATE</div></div>
      <select id="sel-framerate" onchange="pendingRes.fps=parseInt(this.value)">
        <option value="10">10 fps</option>
        <option value="15" selected>15 fps</option>
        <option value="24">24 fps</option>
        <option value="30">30 fps</option>
      </select><div></div>
    </div>
    <div class="btn-row">
      <button class="btn primary" onclick="applyStreamConfig()">⟳ Save + Restart</button>
    </div>
  </div>
  <div class="card">
    <div class="card-title">JPEG quality (live + saved)</div>
    <div class="control-row">
      <div><div class="ctrl-label">Stream quality</div><div class="ctrl-sub">0…99</div></div>
      <input type="range" id="sl-StreamQ" min="0" max="99" step="1" value="75" oninput="upd('StreamQ',this.value)" onchange="sendStreamQ(this.value)">
      <div class="val-display" id="val-StreamQ">75</div>
    </div>
    <div class="control-row">
      <div><div class="ctrl-label">Snapshot quality</div><div class="ctrl-sub">0…99</div></div>
      <input type="range" id="sl-SnapQ" min="0" max="99" step="1" value="96" oninput="upd('SnapQ',this.value)" onchange="sendSnapQ(this.value)">
      <div class="val-display" id="val-SnapQ">96</div>
    </div>
  </div>
</div>

<!-- SYSTEM -->
<div class="panel" id="panel-system">
  <div class="panel-title">System</div>
  <div class="card">
    <div class="card-title">Camera-streamer service</div>
    <p style="color:var(--muted);font-size:13px;margin-bottom:14px;">Resolution and framerate changes require a restart. Camera parameters (exposure, zoom, colour etc.) take effect immediately.</p>
    <div class="btn-row"><button class="btn primary" onclick="restartCamera()">⟳ Restart camera-streamer</button></div>
  </div>
  <div class="card">
    <div class="card-title">Raspberry Pi</div>
    <p style="color:var(--muted);font-size:13px;margin-bottom:14px;">The Pi will be unreachable for ~40–60 seconds after reboot.</p>
    <div class="btn-row"><button class="btn danger" onclick="rebootPi()">⏻ Reboot Raspberry Pi</button></div>
  </div>
</div>

</main>
</div><!-- /main-wrap -->

<!-- Resizer -->
<div class="resizer" id="resizer"></div>

<!-- Camera panel -->
<div class="cam-panel" id="camPanel">
  <div>
    <div class="cam-section-title">Live stream</div>
    <div class="cam-feed" onclick="openFs('stream')">
      <img id="liveStream" src="" alt="stream">
      <div class="cam-badge">LIVE</div>
    </div>
  </div>
  <div>
    <div class="cam-section-title">Snapshot <span id="snapCountdown" style="float:right;color:var(--accent);">10s</span></div>
    <div class="cam-feed" onclick="openFs('snap')">
      <img id="snapImg" src="" alt="snapshot">
      <div class="cam-badge" style="background:rgba(0,0,0,.65);color:var(--accent2);">SNAP</div>
    </div>
    <div class="snap-timer" id="snapTime">—</div>
  </div>
</div>

</div><!-- /layout -->

<!-- Fullscreen overlay -->
<div id="fsOverlay" onclick="closeFs()">
  <img id="fsImg" src="" alt="">
  <div id="fsBadge"></div>
  <button id="fsClose" onclick="closeFs()">✕</button>
</div>

<div id="toast"></div>

<script>
let SENSOR_W=4608, SENSOR_H=2592, currentZoom=1.0, pendingRes={w:1920,h:1080,fps:15};
const HOST = window.location.hostname;

function initFeeds() {
  document.getElementById('liveStream').src = `http://${HOST}:8080/stream`;
}

let snapInterval, snapCountTimer, snapSecsLeft=10;
function refreshSnapshot() {
  document.getElementById('snapImg').src = `http://${HOST}:8080/snapshot?t=${Date.now()}`;
  const now = new Date();
  document.getElementById('snapTime').textContent =
    String(now.getHours()).padStart(2,'0')+':'+
    String(now.getMinutes()).padStart(2,'0')+':'+
    String(now.getSeconds()).padStart(2,'0');
  snapSecsLeft=10;
}
function startSnapTimer() {
  refreshSnapshot();
  snapInterval    = setInterval(refreshSnapshot, 10000);
  snapCountTimer  = setInterval(() => {
    snapSecsLeft--;
    if (snapSecsLeft < 0) snapSecsLeft = 10;
    document.getElementById('snapCountdown').textContent = snapSecsLeft+'s';
  }, 1000);
}

function nav(el) {
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  const id = el.dataset.panel;
  document.getElementById('panel-'+id).classList.add('active');
  document.getElementById('camPanel').classList.toggle('hidden', id==='system');
  document.getElementById('resizer').style.display = id==='system' ? 'none' : '';
}

let _tt;
function toast(msg, err=false) {
  const t=document.getElementById('toast');
  t.textContent=msg; t.className='show'+(err?' err':'');
  clearTimeout(_tt); _tt=setTimeout(()=>t.className='',2600);
}

function upd(id, v) {
  const el=document.getElementById('val-'+id); if(!el) return;
  const fv=parseFloat(v);
  if (id==='ExposureTime')          el.textContent = fv==0?'auto':fv.toFixed(0)+' µs';
  else if (id==='ColourTemperature') el.textContent = fv.toFixed(0)+'K';
  else if (['Brightness','ExposureValue','AnalogueGain','DigitalGain','Contrast',
            'Saturation','Sharpness','LensPosition','ColourGainsR','ColourGainsB'].includes(id))
    el.textContent = fv.toFixed(1);
  else el.textContent = fv.toFixed(0);
}

async function post(url, body) {
  try {
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    return await r.json();
  } catch(e) { return {ok:false}; }
}

async function sendSlider(key,value) { const r=await post('/api/camera_option',{key,value}); toast(r.ok?`✓ ${key} = ${value}`:`✗ ${key} — error`,!r.ok); }
async function sendSelect(key,value) { const r=await post('/api/camera_option',{key,value}); toast(r.ok?`✓ ${key} = ${value}`:`✗ ${key} — error`,!r.ok); }
async function sendToggle(key,value) { const v=value===true?1:value===false?0:value; const r=await post('/api/camera_option',{key,value:v}); toast(r.ok?`✓ ${key} = ${v}`:`✗ ${key} — error`,!r.ok); }
async function sendColourGains() {
  const red=parseFloat(document.getElementById('sl-ColourGainsR').value);
  const blue=parseFloat(document.getElementById('sl-ColourGainsB').value);
  const r=await post('/api/camera_option',{key:'ColourGains',value:`${red},${blue}`});
  toast(r.ok?`✓ ColourGains R=${red.toFixed(2)} B=${blue.toFixed(2)}`:'✗ ColourGains — error',!r.ok);
}
async function sendStreamQ(v) { const r=await post('/api/stream_quality',{value:v}); toast(r.ok?`✓ Stream quality = ${v}`:'✗ Error',!r.ok); }
async function sendSnapQ(v)   { const r=await post('/api/snapshot_quality',{value:v}); toast(r.ok?`✓ Snapshot quality = ${v}`:'✗ Error',!r.ok); }

function calcCrop(z) {
  const cw=Math.round(SENSOR_W/z), ch=Math.round(SENSOR_H/z);
  return {cx:Math.round((SENSOR_W-cw)/2), cy:Math.round((SENSOR_H-ch)/2), cw, ch};
}
function zoomChanged(v) {
  currentZoom=parseFloat(v);
  const {cx,cy,cw,ch}=calcCrop(currentZoom);
  document.getElementById('zoom-label').textContent=currentZoom.toFixed(1)+'×';
  document.getElementById('zoom-crop-info').textContent=`ScalerCrop: ${cx},${cy},${cw},${ch}  (${cw}×${ch} px)`;
  document.querySelectorAll('#panel-zoom .preset-btn').forEach(b=>
    b.classList.toggle('sel',parseFloat(b.textContent)===currentZoom));
}
function setZoom(z,btn) {
  currentZoom=z; document.getElementById('sl-zoom').value=z; zoomChanged(z);
  if(btn){document.querySelectorAll('#panel-zoom .preset-btn').forEach(b=>b.classList.remove('sel'));btn.classList.add('sel');}
}
async function applyZoom() {
  const {cx,cy,cw,ch}=calcCrop(currentZoom);
  const r=await post('/api/camera_option',{key:'ScalerCrop',value:`${cx},${cy},${cw},${ch}`});
  toast(r.ok?`✓ Zoom ${currentZoom.toFixed(1)}× applied`:'✗ ScalerCrop — error',!r.ok);
}

function afModeChanged(v) {
  const row=document.getElementById('row-AfTrigger');
  if(row) row.style.opacity=v==1?'1':'0.4';
}

function setRes(w,h,btn) {
  pendingRes.w=w; pendingRes.h=h;
  document.querySelectorAll('#res-btns .preset-btn').forEach(b=>b.classList.remove('sel'));
  if(btn) btn.classList.add('sel');
  toast(`Resolution: ${w}×${h} — click Save + Restart to apply`);
}
async function applyStreamConfig() {
  const r=await post('/api/stream_config',{WIDTH:pendingRes.w,HEIGHT:pendingRes.h,FRAMERATE:pendingRes.fps});
  if(r.ok){toast('Config saved — restarting...'); setTimeout(()=>restartCamera(),800);}
}

async function restartCamera() {
  toast('⟳ Restarting...');
  const r=await post('/api/restart',{});
  setTimeout(checkStatus,4000);
  setTimeout(()=>{document.getElementById('liveStream').src=`http://${HOST}:8080/stream`;},5000);
  toast(r.ok?'✓ camera-streamer restarted':'✗ Restart failed',!r.ok);
}
async function rebootPi() {
  if(!confirm('Reboot the Raspberry Pi?')) return;
  await post('/api/restart_pi',{});
  toast('⏻ Pi rebooting...');
}

async function checkStatus() {
  try {
    const d=await(await fetch('/api/service_status')).json();
    const ok=d.status==='active';
    document.getElementById('statusDot').className='dot '+(ok?'active':'error');
    document.getElementById('statusText').textContent=ok?'Active':d.status;
  } catch {
    document.getElementById('statusDot').className='dot error';
    document.getElementById('statusText').textContent='Offline';
  }
}

async function loadConfig() {
  try {
    const cfg=await(await fetch('/api/config')).json();
    const cam=cfg.CAMERA_OPTIONS||{};
    if(cfg.SENSOR_W) SENSOR_W=cfg.SENSOR_W;
    if(cfg.SENSOR_H) SENSOR_H=cfg.SENSOR_H;

    const sl=(id,v)=>{if(v==null)return;const e=document.getElementById('sl-'+id);if(e){e.value=v;upd(id,v);}};
    const se=(id,v)=>{if(v==null)return;const e=document.getElementById('sel-'+id);if(e)e.value=String(v);};
    const tog=(id,v)=>{const e=document.getElementById('tog-'+id);if(e)e.checked=(v==1||v===true||v==='true');};

    sl('ExposureValue',cam.ExposureValue??0); sl('ExposureTime',cam.ExposureTime??0);
    sl('AnalogueGain',cam.AnalogueGain??1);   sl('DigitalGain',cam.DigitalGain??1);
    se('AeMeteringMode',cam.AeMeteringMode??0); se('AeExposureMode',cam.AeExposureMode??0);
    se('AeConstraintMode',cam.AeConstraintMode??0); se('HdrMode',cam.HdrMode??0);
    tog('AeEnable',cam.AeEnable??1); tog('AeLock',cam.AeLock??0);

    sl('ColourTemperature',cam.ColourTemperature??5600);
    tog('AwbEnable',cam.AwbEnable??1); tog('AwbLock',cam.AwbLock??0);
    se('AwbMode',cam.AwbMode??0);
    if(cam.ColourGains){const p=String(cam.ColourGains).split(',');if(p.length>=2){sl('ColourGainsR',parseFloat(p[0]));sl('ColourGainsB',parseFloat(p[1]));}}

    sl('Brightness',cam.Brightness??0); sl('Contrast',cam.Contrast??1);
    sl('Saturation',cam.Saturation??1); sl('Sharpness',cam.Sharpness??1);
    se('NoiseReductionMode',cam.NoiseReductionMode??1);

    se('AfMode',cam.AfMode??2); se('AfRange',cam.AfRange??0);
    se('AfSpeed',cam.AfSpeed??0); se('AfMetering',cam.AfMetering??0);
    sl('LensPosition',cam.LensPosition??0); afModeChanged(cam.AfMode??2);

    if(cam.ScalerCrop){const p=String(cam.ScalerCrop).split(',');if(p.length===4){const z=Math.round((SENSOR_W/parseInt(p[2]))*10)/10;setZoom(z,null);document.getElementById('sl-zoom').value=z;}}

    sl('StreamQ',cfg.STREAM_QUALITY??75); sl('SnapQ',cfg.SNAPSHOT_QUALITY??96);
    if(cfg.WIDTH&&cfg.HEIGHT){
      pendingRes={w:cfg.WIDTH,h:cfg.HEIGHT,fps:cfg.FRAMERATE??15};
      document.querySelectorAll('#res-btns .preset-btn').forEach(b=>{
        const[bw,bh]=b.textContent.trim().split('×').map(Number);
        b.classList.toggle('sel',bw===cfg.WIDTH&&bh===cfg.HEIGHT);
      });
    }
    if(cfg.FRAMERATE){const s=document.getElementById('sel-framerate');if(s){s.value=cfg.FRAMERATE;pendingRes.fps=cfg.FRAMERATE;}}
  } catch(e){console.warn('Config load error:',e);}
}

// Resizer
(function(){
  const resizer=document.getElementById('resizer');
  const cam=document.getElementById('camPanel');
  let dragging=false,startX=0,startW=0;
  resizer.addEventListener('mousedown',e=>{
    dragging=true; startX=e.clientX; startW=cam.offsetWidth;
    resizer.classList.add('dragging');
    document.body.style.userSelect='none'; document.body.style.cursor='col-resize';
    const img=document.getElementById('liveStream');
    img.dataset.frozenSrc=img.src; img.src='';
  });
  document.addEventListener('mousemove',e=>{
    if(!dragging) return;
    const newW=Math.min(Math.max(startW+(startX-e.clientX),220),window.innerWidth*0.65);
    cam.style.width=newW+'px';
  });
  document.addEventListener('mouseup',()=>{
    if(!dragging) return;
    dragging=false; resizer.classList.remove('dragging');
    document.body.style.userSelect=''; document.body.style.cursor='';
    const img=document.getElementById('liveStream');
    if(img.dataset.frozenSrc){img.src=img.dataset.frozenSrc;delete img.dataset.frozenSrc;}
  });
})();

// Fullscreen
function openFs(type) {
  const img=document.getElementById('fsImg');
  const badge=document.getElementById('fsBadge');
  img.src = type==='stream' ? `http://${HOST}:8080/stream` : `http://${HOST}:8080/snapshot?t=${Date.now()}`;
  badge.textContent = type==='stream' ? 'Live stream' : 'Snapshot';
  document.getElementById('fsOverlay').classList.add('show');
  document.body.style.overflow='hidden';
}
function closeFs() {
  document.getElementById('fsOverlay').classList.remove('show');
  document.getElementById('fsImg').src='';
  document.body.style.overflow='';
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeFs();});

// Init
initFeeds();
startSnapTimer();
checkStatus();
setInterval(checkStatus,10000);
loadConfig();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("╔════════════════════════════════════════════╗")
    print("║   camera-streamer Web UI                  ║")
    print("║   http://YOUR-PI-IP:5001                  ║")
    print("╚════════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5001, debug=False)

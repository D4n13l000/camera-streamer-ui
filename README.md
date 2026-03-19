# camera-streamer Web UI

A browser-based control panel for **camera-streamer** on **OctoPi (64-bit)** with the **Raspberry Pi Camera Module 3 (IMX708)**.

> Built by [@D4n13l000](https://github.com/D4n13l000)

![screenshot placeholder](docs/screenshot.png)

---

## Why this exists

OctoPi's 64-bit (arm64) build does not ship with working Camera Module 3 support out of the box. Getting `camera-streamer` running on 64-bit OctoPi requires manual setup — and once it runs, there is no GUI to control the camera's many libcamera parameters. This project fills that gap.

If you are running **64-bit OctoPi** and own a **Camera Module 3**, this tool gives you a full web UI to tune every libcamera parameter without touching the terminal.

---

## Features

- **Live MJPEG stream** and **10-second auto-refreshing snapshot** in a resizable side panel
- Full libcamera control:
  - Auto/manual exposure (AE mode, metering, EV, shutter speed, analogue & digital gain)
  - HDR modes (off / multi-exposure / single / night)
  - White balance (AWB mode, lock, colour temperature, R/B gain)
  - Image: brightness, contrast, saturation, sharpness, noise reduction
  - Autofocus: mode (manual / auto / continuous), range, speed, trigger
  - Manual lens position (LensPosition)
  - Digital zoom via **ScalerCrop** with sensor-accurate coordinates (1× – 8×)
- Stream resolution presets (720p / 1080p / 1296p / 4K) and framerate
- JPEG quality control for stream and snapshots (live, no restart needed)
- All settings are **applied live** to the running camera-streamer instance **and** written back to the config file — so they persist across reboots
- Click any feed to open it **fullscreen** (Esc or click to close)
- Resizable camera panel (drag the divider)
- Dark UI, works great on mobile browsers too

---

## Compatibility

| Hardware | OS / Distribution | Status |
|---|---|---|
| Raspberry Pi 3B+ | OctoPi 1.0.0+ **64-bit** (arm64) | ✅ Tested |
| Raspberry Pi 4 | OctoPi 1.0.0+ **64-bit** (arm64) | ✅ Expected to work |
| Raspberry Pi 5 | OctoPi 1.0.0+ **64-bit** (arm64) | 🔶 Not tested |
| Any Pi | OctoPi **32-bit** (armhf) | 🔶 Should work, not tested |
| Any Pi | MainsailOS / FluiddPI / Crowsnest | ❌ Not supported yet |

**Camera:** Raspberry Pi Camera Module 3 (IMX708) only.
Other cameras using camera-streamer + libcamera may work but zoom coordinates (ScalerCrop) will be incorrect unless you edit `SENSOR_W` / `SENSOR_H` in `camera_ui.py`.

**Requires:** `camera-streamer` already installed and running. On OctoPi 1.0.0+ this is the default "New Experimental Camera Stack".

---

## Quick install

```bash
# 1. Clone the repo onto your Pi
git clone https://github.com/D4n13l000/camera-streamer-ui.git
cd camera-streamer-ui

# 2. Run the installer (as root)
sudo bash install.sh
```

The installer will:
- Auto-detect your `camera-streamer` config file path
- Auto-detect the camera API port (8080 by default)
- Choose a free port for the UI (5001 by default, skips 5000 which OctoPrint uses)
- Create a Python virtual environment
- Install Flask and requests
- Write a sudoers rule (so the UI can restart the service and write the config without a password prompt)
- Install and start a systemd service so the UI launches automatically on every boot

After install, open: **`http://<your-pi-ip>:5001`**

---

## Manual install (step by step)

If you prefer to do it yourself or the installer fails:

### 1. Upload `camera_ui.py` to your Pi

Place it at `/home/pi/camera-streamer-ui/camera_ui.py`

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv /home/pi/camera-streamer-ui/venv
/home/pi/camera-streamer-ui/venv/bin/pip install flask requests
```

### 3. Set config file permissions

```bash
sudo chmod 664 /etc/camera-streamer.conf.d/libcamera.conf
sudo chown root:pi /etc/camera-streamer.conf.d/libcamera.conf
```

### 4. Check for port conflicts

OctoPrint occupies port 5000. Verify nothing else uses 5001:

```bash
sudo ss -tlnp | grep 5001
```

If it's taken, edit the last line of `camera_ui.py` and change `port=5001` to something free.

### 5. Create the systemd service

```bash
sudo nano /etc/systemd/system/camera-streamer-ui.service
```

```ini
[Unit]
Description=camera-streamer Web UI
After=network.target camera-streamer-libcamera.service

[Service]
ExecStart=/home/pi/camera-streamer-ui/venv/bin/python /home/pi/camera-streamer-ui/camera_ui.py
WorkingDirectory=/home/pi/camera-streamer-ui
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable camera-streamer-ui
sudo systemctl start camera-streamer-ui
```

### 6. Verify

```bash
sudo systemctl status camera-streamer-ui
```

---

## Uninstall

```bash
sudo systemctl stop camera-streamer-ui
sudo systemctl disable camera-streamer-ui
sudo rm /etc/systemd/system/camera-streamer-ui.service
sudo rm /etc/sudoers.d/camera-streamer-ui
sudo systemctl daemon-reload
rm -rf ~/camera-streamer-ui
```

---

## Troubleshooting

**UI loads but stream is black / not showing**
- Check that camera-streamer is running: `sudo systemctl status camera-streamer-libcamera`
- Verify the stream is accessible: `curl http://localhost:8080/stream -I`

**"Permission denied" when saving settings**
- The installer writes a sudoers rule. If you installed manually, check that `/etc/sudoers.d/camera-streamer-ui` exists and the config file is owned by `root:pi` with mode `664`.

**Port 5001 already in use**
- Edit `camera_ui.py`, change `port=5001` in the last line, then `sudo systemctl restart camera-streamer-ui`.

**Settings don't persist after reboot**
- Check that the config file path in `camera_ui.py` matches your actual config: `grep CONFIG_PATH camera_ui.py`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

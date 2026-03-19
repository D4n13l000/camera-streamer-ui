# Contributing

Contributions are welcome. Here's how to help.

## Bug reports

Open an issue and include:
- Your Pi model and OctoPi version (`cat /etc/octopi_version`)
- Architecture: `uname -m` (should be `aarch64` for 64-bit)
- Camera module version
- Output of `sudo systemctl status camera-streamer-libcamera`
- Output of `sudo systemctl status camera-streamer-ui`
- The exact error or unexpected behaviour

## Pull requests

1. Fork the repo
2. Create a branch: `git checkout -b my-fix`
3. Make your changes
4. Test on a real Pi with Camera Module 3 if possible
5. Open a PR with a short description of what changed and why

## Areas where help is especially welcome

- **Crowsnest / MainsailOS support** — the config format differs (INI vs shell), auto-detection logic needs testing
- **Other camera modules** — HQ Camera (IMX477), Camera Module 2 (IMX219) have different sensor resolutions; ScalerCrop values would need updating
- **Raspberry Pi 5 testing** — not yet verified
- **Mobile layout improvements**

## Code style

- Python: follow the existing style (no external linter config)
- Keep the entire UI in a single `.py` file — the point is a zero-dependency drop-in
- All user-facing text in English

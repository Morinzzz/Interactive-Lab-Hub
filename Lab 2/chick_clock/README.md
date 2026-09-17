# Chick Clock

Full Lab 2 Part 2 clock for the Adafruit Mini PiTFT.

## Run on the Pi

```bash
cd ~/Interactive-Lab-Hub/Lab\ 2/chick_clock
source ~/venv/bin/activate
sudo systemctl stop piscreen.service --now
python chick_clock.py
```

## Controls

- **A tap** — start/stop 30-minute focus timer
- **B tap** — strike the hour / announce the time (ignored while an announcement is still playing)
- **B hold** — detail screen (time, date, school-year progress)
- **A + B** — step through scene preview

## Files

| File | Role |
|------|------|
| `chick_clock.py` | Main app (display + buttons) |
| `chick_scene.py` | Frame renderer |
| `chick_art.py` | Chick sprites and text |
| `chick_sound.py` | Hour strikes and spoken time |
| `chick_preview.py` | Laptop preview (Pillow only) |

Laptop preview (no Pi needed):

```bash
python chick_preview.py
```

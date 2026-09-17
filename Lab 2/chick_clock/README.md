# Chick Clock

Lab 2 Part 2 clock for the Adafruit Mini PiTFT.

Lives at `Lab 2/chick_clock/`. It uses its own `chick_*` modules and can also
import other scripts from the parent `Lab 2/` folder (not `iclock/`).

## Layout

```text
Lab 2/
  requirements.txt          ← shared deps
  screen_test.py            ← etc. (usable from chick_clock)
  chick_clock/              ← this project
    chick_clock.py
    chick_sound.py
    chick_scene.py
    chick_art.py
    chick_preview.py
  iclock/                   ← separate; not used by Chick Clock
```

## Run on the Pi

```bash
cd ~/Interactive-Lab-Hub/Lab\ 2/chick_clock
source ~/venv/bin/activate
pip install -r ../requirements.txt   # once, if needed
sudo systemctl stop piscreen.service --now
python chick_clock.py
```

## Controls

- **A tap** — start/stop 30-minute focus timer
- **B tap** — strike the hour / announce time (ignored while an announcement is still playing)
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

Laptop preview:

```bash
cd chick_clock
python chick_preview.py
```

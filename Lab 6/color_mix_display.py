# Color mixing - shared screen
# Listens to all three players over MQTT, mixes their colors, and shows them on a web page.
# Run:  python color_mix_display.py --port 8091   then open http://localhost:8091

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import paho.mqtt.client as mqtt

BROKER = "farlab.infosci.cornell.edu"
PORT = 1883
USER = "idd"
PASSWORD = "device@theFarm"

parser = argparse.ArgumentParser()
parser.add_argument("--team", default="morinmig")
parser.add_argument("--port", type=int, default=8080)
args = parser.parse_args()

TOPIC = f"IDD/{args.team}/colormix/+"

players = {}
lock = threading.Lock()


def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)
    print("Connected, listening on", TOPIC)


def on_message(client, userdata, msg):
    try:
        d = json.loads(msg.payload)
        with lock:
            players[int(d["player"])] = {"r": d["r"], "g": d["g"], "b": d["b"],
                                         "present": d["present"], "seen": time.time()}
    except (ValueError, KeyError, TypeError):
        pass  # ignore messages we can't read


def get_state():
    now = time.time()
    result = {}
    active = []
    with lock:
        for n in (1, 2, 3):
            p = players.get(n)
            online = p is not None and now - p["seen"] < 3   # offline after 3 s of no messages
            holding = online and p["present"]
            result[n] = {"online": online, "holding": holding}
            if online:
                result[n].update(r=p["r"], g=p["g"], b=p["b"])
            if holding:
                active.append(p)

    mix = None
    if active:
        # average of everyone holding a color, like mixing light
        mix = {k: round(sum(p[k] for p in active) / len(active)) for k in "rgb"}
    return {"players": result, "mix": mix, "count": len(active)}


PAGE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Color Mix</title>
<style>
  body { margin: 0; min-height: 100vh; background: #141418; color: #eee; font: 18px sans-serif;
         display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 28px; }
  h1 { margin: 0; }
  .row { display: flex; align-items: center; justify-content: center; gap: 20px; flex-wrap: wrap; }
  .tile { display: flex; flex-direction: column; align-items: center; gap: 10px; width: 170px; }
  .swatch { width: 150px; height: 150px; border-radius: 50%; background: #2a2a31; border: 3px solid #3a3a44; }
  .mix { width: 290px; }
  .mix .swatch { width: 260px; height: 260px; }
  .name { font-weight: bold; }
  .info { color: #aaa; font-size: 15px; text-align: center; white-space: pre-line; min-height: 2.6em; }
  .op { font-size: 44px; color: #666; }
</style>
</head>
<body>
<h1>Color Mix</h1>
<div class="row">
  <div class="tile" id="p1"><div class="swatch"></div><div class="name">Player 1</div><div class="info"></div></div>
  <div class="op">+</div>
  <div class="tile" id="p2"><div class="swatch"></div><div class="name">Player 2</div><div class="info"></div></div>
  <div class="op">+</div>
  <div class="tile" id="p3"><div class="swatch"></div><div class="name">Player 3</div><div class="info"></div></div>
  <div class="op">=</div>
  <div class="tile mix" id="mix"><div class="swatch"></div><div class="name">Mixed color</div><div class="info"></div></div>
</div>
<script>
function hex(c) {
  return "#" + [c.r, c.g, c.b].map(v => v.toString(16).padStart(2, "0")).join("").toUpperCase();
}

function show(id, color, text) {
  const el = document.getElementById(id);
  el.querySelector(".swatch").style.background = color ? hex(color) : "#2a2a31";
  el.querySelector(".info").textContent = text;
}

async function update() {
  try {
    const s = await (await fetch("/state", {cache: "no-store"})).json();
    for (const n of [1, 2, 3]) {
      const p = s.players[n];
      if (!p.online) show("p" + n, null, "offline");
      else if (!p.holding) show("p" + n, null, "hold a color up");
      else show("p" + n, p, hex(p) + "\nRGB " + p.r + ", " + p.g + ", " + p.b);
    }
    if (s.mix) show("mix", s.mix, hex(s.mix) + " (mix of " + s.count + ")");
    else show("mix", null, "waiting for colors");
  } catch (e) {}
}

setInterval(update, 150);
update();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.reply(PAGE.encode(), "text/html")
        elif self.path == "/state":
            self.reply(json.dumps(get_state()).encode(), "application/json")
        else:
            self.send_error(404)

    def reply(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep the terminal quiet


client = mqtt.Client()
client.username_pw_set(USER, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

print(f"Open http://localhost:{args.port}")
try:
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
except KeyboardInterrupt:
    pass

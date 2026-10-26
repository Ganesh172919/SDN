"""SELF-X network operations console: a 1990s-style Tk front end for live.engine.

Every number on screen comes from live.engine.Session, i.e. the project's own
fluid model and controllers. A shadow A0 session runs the identical traffic so
"packets saved" is always measured against doing nothing.

    .venv\\Scripts\\python.exe -m live            (from selfx/)
"""
from __future__ import annotations
import csv
import random
import re
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

from live.engine import Session, CONTROLLERS, SCENARIOS, PACKETS_PER_MBIT, HEADROOMS, BUFFER, INTERVAL

# Chrome (Windows 3.x/95 grey) and CRT phosphor palette.
GREY, SHADOW, HILITE, INKC = "#c0c0c0", "#808080", "#ffffff", "#000000"
CRT, GRID, GREEN, DIMG = "#000000", "#0c2a12", "#33ff66", "#1d8a3c"
AMBER, RED, CYAN, PALE, FAINT = "#ffb000", "#ff4a3d", "#46d2ff", "#d8ffe0", "#5f7a66"
DOT_MBIT = 1.0  # one moving dot = 1 Mbit of traffic

# Network map geometry at 96 dpi (scaled by S at runtime).
MAP_W, MAP_H = 790, 400
NODES = {"h1": (62, 110), "h2": (62, 280), "s1": (215, 195), "s2": (400, 100), "s3": (400, 290),
         "s4": (655, 195), "h7": (748, 110), "h8": (748, 280), "xt": (400, 352)}
TANK = {0: (525, 100), 1: (525, 290)}
BIN = {0: (525, 40), 1: (620, 352), "meter": (150, 345)}
SCENARIO_HELP = {"mixed": "light / burst / alt busy / both busy, repeating", "flash": "sudden elephant bursts on primary",
                 "alternate": "alternate path is always busy", "shift": "alternate gets busy halfway through",
                 "overload": "both paths overloaded (nothing can help)", "light": "nothing is congested",
                 "recurring": "six traffic patterns that repeat", "volatile": "random traffic every window"}
CONTROLLER_RULE = {
    "A0": "never acts: every packet stays on the primary path",
    "B1": "reroute if alternate is less loaded and fits 90%",
    "H1": "fits? leave it | alt fits 90%? reroute | else meter 80%",
    "H2": "same rule; capacity-aware meter, 0.1 Mbps headroom",
    "A4": "same rule; memory picks meter headroom 0.0/0.1/0.3",
    "O2": "tries every action on the model, keeps best (cheats)",
}
HELP_TEXT = """WHAT AM I LOOKING AT?

Two paths connect s1 to s4. Each bottleneck carries 10 Mbit/s and has a
0.5 Mbit buffer (the tank). Background traffic uses both paths. One
'elephant' flow (h2 -> h8, amber dots) starts on the primary path in
every 5-second window.

Each window the controller:
  1 OBSERVE  reads the loads and queues
  2 DECIDE   no_op, reroute (move elephant to s3) or rate_limit (meter it)
  3 GUARD    an independent safety check can veto the action
  4 INSTALL  a simulated OpenFlow rule on s1, expiring after 5 s
  5 OUTCOME  the fluid model computes queues, delay and drops

Dots: green = background, amber = elephant, red = dropped.
1 dot = 1 Mbit, about 83 packets of 1500 bytes.
A full tank overflows into the OVERFLOW bin; a meter deliberately
trims at most 20% of the elephant into the METER bin.

PACKETS SAVED compares against a hidden A0 run (no control) on the
identical traffic. It can go negative: metering throws traffic away
on purpose to cut queueing delay.

Keys: Space run/pause | N or Right step | R reset | F1 this help

Network values are a fluid model, not a packet capture. The controllers
and the model are the project's own code (selfx/eval, selfx/agent)."""


def pick_font(root, names, size, weight="normal"):
    families = set(tkfont.families(root))
    return next(((n, size, weight) for n in names if n in families), ("TkFixedFont", size, weight))


class Console:
    def __init__(self, root: tk.Tk):
        self.root = root
        dpi = max(1.0, root.winfo_fpixels("1i") / 96)
        # Map/scope geometry follows DPI but never outgrows the screen; text follows DPI via point sizes.
        self.S = min(dpi, root.winfo_screenwidth() * .58 / MAP_W, root.winfo_screenheight() * .44 / MAP_H)
        crisp = dpi < 1.2
        self.ui = pick_font(root, ["MS Sans Serif", "Microsoft Sans Serif", "Tahoma"] if crisp else ["Tahoma", "Segoe UI"], 8)
        self.ui_bold = (*self.ui[:2], "bold")
        self.mono = pick_font(root, ["Lucida Console", "Consolas", "Courier New"], 9)
        self.mono_small = pick_font(root, ["Lucida Console", "Consolas", "Courier New"], 8)
        self.vars = {"controller": tk.StringVar(value="A4"), "scenario": tk.StringVar(value="mixed"),
                     "seed": tk.StringVar(value="1900"), "speed": tk.IntVar(value=8), "packets": tk.BooleanVar(value=True)}
        self.running, self.dots, self.anim_end, self.window = False, [], 0.0, None
        self.rng = random.Random(7)
        root.title("SELF-X Network Operations Console")
        root.configure(bg=GREY)
        root.option_add("*Font", self.ui)
        self._menu()
        self._toolbar()
        self._body()
        self._status()
        for key, fn in (("<space>", lambda e: self.toggle()), ("<Right>", lambda e: self.step()),
                        ("n", lambda e: self.step()), ("r", lambda e: self.reset()), ("<F1>", lambda e: self.help())):
            root.bind(key, fn)
        self.reset()
        self._frame()

    # ------------------------------------------------------------- chrome
    def p(self, v):
        return v * self.S

    def bevel(self, parent, sunken=True, **kw):
        return tk.Frame(parent, bg=GREY, relief=tk.SUNKEN if sunken else tk.RAISED, bd=2, **kw)

    def _menu(self):
        bar = tk.Menu(self.root, tearoff=0)
        f = tk.Menu(bar, tearoff=0)
        f.add_command(label="Export run log (CSV)...", command=self.export)
        f.add_separator()
        f.add_command(label="Exit", command=self.root.destroy)
        s = tk.Menu(bar, tearoff=0)
        s.add_command(label="Run / Pause", accelerator="Space", command=self.toggle)
        s.add_command(label="Step one window", accelerator="N", command=self.step)
        s.add_command(label="Reset", accelerator="R", command=self.reset)
        s.add_separator()
        for label, value in (("Real time (1x)", 1), ("Fast (8x)", 8), ("Very fast (25x)", 25), ("Max, no packets (60x)", 60)):
            s.add_command(label=label, command=lambda v=value: self.vars["speed"].set(v))
        h = tk.Menu(bar, tearoff=0)
        h.add_command(label="What am I looking at?", accelerator="F1", command=self.help)
        h.add_command(label="About...", command=lambda: messagebox.showinfo(
            "About", "SELF-X Network Operations Console\nEC466 Software Defined Networks, team SDN_07\n\n"
                     "Replays the project's fluid model and controllers window by window."))
        for label, menu in (("File", f), ("Simulation", s), ("Help", h)):
            bar.add_cascade(label=label, menu=menu)
        self.root.config(menu=bar)

    def _toolbar(self):
        bar = tk.Frame(self.root, bg=GREY, relief=tk.RAISED, bd=2)
        bar.pack(fill=tk.X)
        def label(text):
            tk.Label(bar, text=text, bg=GREY).pack(side=tk.LEFT, padx=(8, 2), pady=4)
        def option(var, values):
            menu = tk.OptionMenu(bar, var, *values, command=lambda _: self.reset())
            menu.config(bg=GREY, activebackground=GREY, relief=tk.RAISED, bd=2, highlightthickness=0, width=4, anchor="w")
            menu.pack(side=tk.LEFT)
        label("Controller:"); option(self.vars["controller"], CONTROLLERS)
        label("Scenario:"); option(self.vars["scenario"], SCENARIOS)
        self.vars["scenario"].trace_add("write", lambda *_: None)
        label("Seed:")
        seed = tk.Spinbox(bar, from_=1900, to=1999, width=5, textvariable=self.vars["seed"], command=self.reset,
                          relief=tk.SUNKEN, bd=2, bg=HILITE)
        seed.bind("<Return>", lambda e: self.reset())
        seed.pack(side=tk.LEFT)
        tk.Frame(bar, width=14, bg=GREY).pack(side=tk.LEFT)
        self.run_btn = tk.Button(bar, text="Run", width=7, command=self.toggle, bg=GREY, relief=tk.RAISED, bd=2)
        self.run_btn.pack(side=tk.LEFT, padx=2)
        for text, cmd in (("Step", self.step), ("Reset", self.reset)):
            tk.Button(bar, text=text, width=7, command=cmd, bg=GREY, relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=2)
        label("Speed:")
        tk.Scale(bar, from_=1, to=60, orient=tk.HORIZONTAL, variable=self.vars["speed"], length=self.p(130), showvalue=True,
                 bg=GREY, highlightthickness=0, troughcolor=SHADOW, sliderlength=self.p(14), bd=1).pack(side=tk.LEFT)
        tk.Label(bar, text="x real time", bg=GREY).pack(side=tk.LEFT)
        tk.Checkbutton(bar, text="Show packets", variable=self.vars["packets"], bg=GREY,
                       activebackground=GREY).pack(side=tk.LEFT, padx=10)
        self.scenario_note = tk.Label(bar, text="", bg=GREY, fg=SHADOW)
        self.scenario_note.pack(side=tk.RIGHT, padx=8)

    def panel(self, parent, title):
        outer = tk.Frame(parent, bg=GREY)
        tk.Label(outer, text=title, bg=GREY, font=self.ui_bold, anchor="w").pack(fill=tk.X, padx=2)
        well = self.bevel(outer)
        well.pack(fill=tk.BOTH, expand=True)
        return outer, well

    def _body(self):
        body = tk.Frame(self.root, bg=GREY)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))
        top = tk.Frame(body, bg=GREY)
        top.pack(fill=tk.BOTH, expand=True)
        outer, well = self.panel(top, "Network map  (s1 rule changes every 5 simulated seconds)")
        outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.net = tk.Canvas(well, width=self.p(MAP_W), height=self.p(MAP_H), bg=CRT, highlightthickness=0)
        self.net.pack()
        outer, well = self.panel(top, "Controller trace  (why it did what it did)")
        outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.trace = tk.Text(well, bg=CRT, fg=GREEN, font=self.mono, width=54, height=10, bd=0, wrap=tk.WORD,
                             insertbackground=GREEN, padx=6, pady=4)
        self.trace.pack(fill=tk.BOTH, expand=True)
        for tag, color in (("h", PALE), ("g", GREEN), ("a", AMBER), ("r", RED), ("c", CYAN), ("d", FAINT)):
            self.trace.tag_configure(tag, foreground=color)

        scopes = tk.Frame(body, bg=GREY)
        scopes.pack(fill=tk.X, pady=(6, 0))
        self.scopes = {}
        for key, title in (("delay", "Delay, ms"), ("loss", "Loss, % of offered"), ("saved", "Packets saved vs A0 (cumulative)")):
            outer, well = self.panel(scopes, title)
            outer.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0 if key == "delay" else 6, 0))
            c = tk.Canvas(well, height=self.p(125), width=self.p(300), bg=CRT, highlightthickness=0)
            c.pack(fill=tk.X)
            c.bind("<Configure>", lambda e: self.draw_scopes())
            self.scopes[key] = c

        outer, well = self.panel(body, "Event log")
        outer.pack(fill=tk.X, pady=(6, 0))
        self.log = tk.Listbox(well, bg=CRT, fg=GREEN, font=self.mono_small, height=5, bd=0, highlightthickness=0,
                              selectbackground=DIMG, activestyle="none")
        sb = tk.Scrollbar(well, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.pack(fill=tk.X)

    def _status(self):
        bar = tk.Frame(self.root, bg=GREY)
        bar.pack(fill=tk.X, padx=4, pady=4)
        self.status = []
        for width in (16, 14, 30, 24, 30):
            cell = tk.Label(bar, text="", bg=GREY, relief=tk.SUNKEN, bd=1, anchor="w", width=width, padx=4)
            cell.pack(side=tk.LEFT, padx=1)
            self.status.append(cell)
        self.status_msg = tk.Label(bar, text="", bg=GREY, relief=tk.SUNKEN, bd=1, anchor="w", padx=4)
        self.status_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

    # ------------------------------------------------------------- session
    def reset(self):
        self.running = False
        self.run_btn.config(text="Run", relief=tk.RAISED)
        try:
            seed = int(self.vars["seed"].get())
        except ValueError:
            seed = 1900
            self.vars["seed"].set("1900")
        for name in ("session", "shadow"):
            if getattr(self, name, None):
                getattr(self, name).close()
        c, sc = self.vars["controller"].get(), self.vars["scenario"].get()
        self.session = Session(c, sc, seed)
        self.shadow = Session("A0", sc, seed)
        self.window, self.dots, self.anim_end = None, [], 0.0
        self.bins = {0: 0.0, 1: 0.0, "meter": 0.0}
        self.scenario_note.config(text=f"{sc}: {SCENARIO_HELP[sc]}")
        self.log.delete(0, tk.END)
        self.log.insert(tk.END, f" SESSION  controller {c} ({CONTROLLERS[c]})  scenario {sc}  seed {seed}  "
                                f"120 windows x 5 s")
        self.draw_network(None, 0)
        self.trace.config(state=tk.NORMAL)
        self.trace.delete("1.0", tk.END)
        self.trace.insert(tk.END, "READY.\n\n", "h")
        self.trace.insert(tk.END, f"Controller {c}: {CONTROLLERS[c]}\n  {CONTROLLER_RULE[c]}\n\n", "g")
        self.trace.insert(tk.END, "Press Run (Space) or Step (N).\nF1 explains every part of this screen.", "d")
        self.trace.config(state=tk.DISABLED)
        self.draw_scopes()
        self.update_status("Ready")

    def toggle(self):
        if self.session.done:
            self.reset()
        self.running = not self.running
        self.run_btn.config(text="Pause" if self.running else "Run", relief=tk.SUNKEN if self.running else tk.RAISED)
        if self.running and time.monotonic() >= self.anim_end:
            self.advance()

    def step(self):
        if self.running:
            self.toggle()
        if not self.session.done:
            self.advance()

    def advance(self):
        if self.session.done:
            self.running = False
            self.run_btn.config(text="Run", relief=tk.RAISED)
            self.finish()
            return
        w = self.session.step()
        self.shadow.step()
        self.window = w
        duration = 5.0 / max(1, self.vars["speed"].get())
        self.anim_start, self.anim_end = time.monotonic(), time.monotonic() + duration
        self.spawn_dots(w, duration)
        self.render_trace(w)
        self.write_log(w)
        self.draw_scopes()
        self.update_status("Running" if self.running else "Stepped one window")

    def finish(self):
        h, z = self.session.history, self.shadow.history
        mean = lambda xs: sum(xs) / len(xs)
        saved = (sum(w.dropped_mbit for w in z) - sum(w.dropped_mbit for w in h)) * PACKETS_PER_MBIT
        self.log.insert(tk.END, f" END OF TRACE  delay {mean([w.latency_ms for w in h]):.2f} ms (A0 {mean([w.latency_ms for w in z]):.2f})"
                                f"  loss {mean([w.loss_pct for w in h]):.2f}% (A0 {mean([w.loss_pct for w in z]):.2f})"
                                f"  packets saved {saved:+,.0f}")
        self.log.see(tk.END)
        self.update_status("Trace finished: Reset or change controller")

    # ------------------------------------------------------------- network map
    def node(self, name, label, sub=""):
        x, y = (self.p(v) for v in NODES[name])
        w, h = self.p(26 if name.startswith("s") else 20), self.p(16 if name.startswith("s") else 12)
        self.net.create_rectangle(x - w, y - h, x + w, y + h, outline=GREEN, width=1, fill=CRT, tags="static")
        self.net.create_text(x, y, text=label, fill=PALE, font=self.mono, tags="static")
        if sub:
            self.net.create_text(x, y + h + self.p(9), text=sub, fill=FAINT, font=self.mono_small, tags="static")

    def link_color(self, util):
        return GREEN if util < .7 else AMBER if util <= 1.0 else RED

    def draw_network(self, w, frac):
        c, P = self.net, self.p
        c.delete("static", "live")
        for gx in range(0, MAP_W + 10, 40):
            c.create_line(P(gx), 0, P(gx), P(MAP_H), fill="#06140a", tags="static")
        for gy in range(0, MAP_H + 10, 40):
            c.create_line(0, P(gy), P(MAP_W), P(gy), fill="#06140a", tags="static")
        paths = w.paths if w else None
        utils = [paths[i].arrival_mbps / 10 if paths else 0 for i in (0, 1)]
        for i, (sw, ty) in enumerate((("s2", NODES["s2"][1]), ("s3", NODES["s3"][1]))):
            col = self.link_color(utils[i]) if paths else DIMG
            pts = [NODES["s1"], NODES[sw], TANK[i], NODES["s4"]]
            for a, b in zip(pts, pts[1:]):
                c.create_line(P(a[0]), P(a[1]), P(b[0]), P(b[1]), fill=col, width=P(2), tags="static")
            name = "PRIMARY  s1:2 > s2 > s4" if i == 0 else "ALTERNATE  s1:3 > s3 > s4"
            c.create_text(P(272), P(ty - 22 if i == 0 else ty + 22), text=name, fill=FAINT, font=self.mono_small, tags="static")
        for a, b in (("h1", "s1"), ("h2", "s1"), ("s4", "h7"), ("s4", "h8"), ("xt", "s3")):
            (x0, y0), (x1, y1) = NODES[a], NODES[b]
            c.create_line(P(x0), P(y0), P(x1), P(y1), fill=DIMG, width=P(1), tags="static")
        self.node("h1", "h1", "steady flows"); self.node("h2", "h2", "elephant")
        self.node("h7", "h7"); self.node("h8", "h8")
        self.node("s1", "s1"); self.node("s2", "s2"); self.node("s3", "s3"); self.node("s4", "s4")
        self.node("xt", "xt")
        c.create_text(P(374), P(352), text="cross traffic", anchor="e", fill=FAINT, font=self.mono_small, tags="static")
        for key, label in ((0, "OVERFLOW"), (1, "OVERFLOW"), ("meter", "METER DROP")):
            x, y = (P(v) for v in BIN[key])
            c.create_rectangle(x - P(46), y - P(10), x + P(46), y + P(10), outline=RED, dash=(2, 2), tags="static")
            c.create_text(x, y, text=f"{label} {self.bins[key]:5.1f}Mb", fill=RED, font=self.mono_small, tags="static")
        legend = (("background", GREEN), ("elephant", AMBER), ("dropped", RED))
        x0 = MAP_W - 10
        c.create_text(P(x0), P(MAP_H - 10), anchor="e", fill=FAINT, font=self.mono_small, tags="static",
                      text="1 dot = 1 Mbit = 83 pkts")
        for i, (label, color) in enumerate(legend):
            y = MAP_H - 58 + i * 14
            c.create_rectangle(P(x0 - 92), P(y - 3), P(x0 - 86), P(y + 3), fill=color, outline="", tags="static")
            c.create_text(P(x0 - 80), P(y), anchor="w", text=label, fill=FAINT, font=self.mono_small, tags="static")
        self.draw_live(w, frac)

    def draw_live(self, w, frac):
        c, P = self.net, self.p
        c.delete("live")
        for i in (0, 1):
            x, y = (P(v) for v in TANK[i])
            q = BUFFER * 0 if not w else w.paths[i].queue_before + (w.paths[i].queue_after - w.paths[i].queue_before) * frac
            level = q / BUFFER
            h = P(46)
            color = GREEN if level < .5 else AMBER if level < .9 else RED
            c.create_rectangle(x - P(9), y - h / 2, x + P(9), y + h / 2, outline=PALE, fill=CRT, tags="live")
            if level > 0:
                c.create_rectangle(x - P(8), y + h / 2 - h * level, x + P(8), y + h / 2, fill=color, outline="", tags="live")
            c.create_text(x + P(14), y + (P(-14) if i == 0 else P(14)), anchor="w", fill=PALE, font=self.mono_small,
                          text=f"Q {q:.2f}/{BUFFER:.1f}", tags="live")
            if w:
                util = w.paths[i].arrival_mbps / 10
                c.create_text(x + P(14), y + (P(2) if i == 0 else P(-2)), anchor="w", fill=self.link_color(util),
                              font=self.mono_small, text=f"{w.paths[i].arrival_mbps:4.1f}Mb/s {100 * util:3.0f}%", tags="live")
        if w:
            act = w.installed.action
            sx, sy = (P(v) for v in NODES["s1"])
            text = (f"RULE: meter {w.installed.rate_limit_kbps / 1000:.2f}Mb/s, port 2" if act == "rate_limit" else
                    "RULE: elephant -> port 3" if act == "reroute" else "RULE: none (default port 2)")
            color = {"no_op": FAINT, "reroute": CYAN, "rate_limit": AMBER}[act]
            c.create_text(P(10), P(32), anchor="w", text="s1 " + text, fill=color, font=self.mono_small, tags="live")
            if act != "no_op":  # mark the switch that holds the rule
                c.create_rectangle(sx - P(29), sy - P(19), sx + P(29), sy + P(19), outline=color, width=P(1), tags="live")
            if not w.guard_allowed:
                c.create_text(P(10), P(46), anchor="w", text="GUARD VETO: " + w.guard_reason[:40], fill=RED,
                              font=self.mono_small, tags="live")
            c.create_text(P(10), P(14), anchor="w", fill=PALE, font=self.mono,
                          text=f"W{w.cycle + 1:03d}  t={w.cycle * 5:03d}-{(w.cycle + 1) * 5:03d}s  {w.phase}", tags="live")

    # ------------------------------------------------------------- packets
    def spawn_dots(self, w, duration):
        for d in self.dots:
            self.net.delete(d["id"])
        self.dots = []
        if not self.vars["packets"].get() or duration < .25:
            for i in (0, 1):
                self.bins[i] += w.paths[i].overflow_mbit
            self.bins["meter"] += w.meter_drop_mbit
            return
        d, e = w.demand, w.demand["elephant_mbps"]
        admitted = e * INTERVAL - w.meter_drop_mbit
        jobs = []
        for i, flow in enumerate(w.paths):
            bg = d["primary_background_mbps" if i == 0 else "alternate_background_mbps"] * INTERVAL
            arrivals = [("bg", i)] * round(bg / DOT_MBIT)
            if flow.carries_elephant:
                arrivals += [("el", i)] * round(admitted / DOT_MBIT)
            drops = set(self.rng.sample(range(len(arrivals)), min(len(arrivals), round(flow.overflow_mbit / DOT_MBIT))))
            jobs += [(kind, path, "overflow" if k in drops else "deliver", flow.overflow_mbit / max(1, len(drops)))
                     for k, (kind, path) in enumerate(arrivals)]
        meter_n = round(w.meter_drop_mbit / DOT_MBIT)
        jobs += [("el", None, "meter", w.meter_drop_mbit / max(1, meter_n))] * meter_n
        if not jobs:
            return
        travel = duration * .42
        for kind, path, fate, mbit in jobs:
            start = self.anim_start + self.rng.uniform(0, duration * .55)
            route = self.route(kind, path, fate)
            dwell = 0 if fate == "meter" else duration * .25 * (w.paths[path].queue_after / BUFFER)
            color = AMBER if kind == "el" else GREEN
            size = self.p(2)
            dot = self.net.create_rectangle(-10, -10, -10 + 2 * size, -10 + 2 * size, fill=color, outline="")
            self.dots.append(dict(id=dot, start=start, route=route, travel=travel, dwell=dwell, fate=fate, mbit=mbit,
                                  path=path, color=color, done=False, size=size))

    def route(self, kind, path, fate):
        src = NODES["h2" if kind == "el" else "h1"]
        if kind == "bg" and path == 1:
            src = NODES["xt"]
        if fate == "meter":
            return [src, NODES["s1"], BIN["meter"]], 99
        pts = [src] if (kind == "bg" and path == 1) else [src, NODES["s1"]]
        pts += [NODES["s2" if path == 0 else "s3"], TANK[path]]
        tank_index = len(pts) - 1
        pts += [BIN[path]] if fate == "overflow" else [NODES["s4"], NODES["h8" if kind == "el" else "h7"]]
        return pts, tank_index

    def place(self, dot, now):
        pts, tank_at = dot["route"]
        t = now - dot["start"]
        if t < 0:
            return None
        lengths = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** .5 for a, b in zip(pts, pts[1:])]
        total = sum(lengths) or 1
        speed = total / dot["travel"]
        travelled = t * speed
        before_tank = sum(lengths[:tank_at]) if tank_at < 99 else total
        if travelled > before_tank:  # wait in the tank, proportional to its queue
            travelled = before_tank + max(0.0, (t - before_tank / speed - dot["dwell"]) * speed)
        if travelled >= total:
            return "done"
        for (a, b), seg in zip(zip(pts, pts[1:]), lengths):
            if travelled <= seg:
                f = travelled / seg if seg else 1
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, pts.index(b) == len(pts) - 1
            travelled -= seg
        return "done"

    def _frame(self):
        now = time.monotonic()
        w = self.window
        if w is not None:
            frac = 1.0 if self.anim_end <= self.anim_start else min(1.0, (now - self.anim_start) / (self.anim_end - self.anim_start))
            changed = False
            for dot in self.dots:
                if dot["done"]:
                    continue
                pos = self.place(dot, now)
                if pos is None:
                    continue
                if pos == "done":
                    dot["done"] = True
                    self.net.coords(dot["id"], -10, -10, -9, -9)
                    if dot["fate"] != "deliver":
                        self.bins[dot["path"] if dot["fate"] == "overflow" else "meter"] += dot["mbit"]
                        changed = True
                    continue
                x, y, final_leg = pos
                if dot["fate"] != "deliver" and final_leg:
                    self.net.itemconfig(dot["id"], fill=RED)
                s = dot["size"]
                self.net.coords(dot["id"], self.p(x) - s, self.p(y) - s, self.p(x) + s, self.p(y) + s)
            if changed:
                self.draw_network(w, frac)
            else:
                self.draw_live(w, frac)
            for dot in self.dots:
                self.net.tag_raise(dot["id"])
            if self.running and now >= self.anim_end:
                self._flush_dots()
                self.advance()
        self.root.after(33, self._frame)

    def _flush_dots(self):
        for dot in self.dots:
            if not dot["done"] and dot["fate"] != "deliver":
                self.bins[dot["path"] if dot["fate"] == "overflow" else "meter"] += dot["mbit"]
            self.net.delete(dot["id"])
        self.dots = []

    # ------------------------------------------------------------- text panels
    def render_trace(self, w):
        T = self.trace
        T.config(state=tk.NORMAL)
        T.delete("1.0", tk.END)
        put = lambda text, tag="g": T.insert(tk.END, text, tag)
        d, ctrl = w.demand, self.session.controller
        put(f"WINDOW {w.cycle + 1:03d}/{len(self.session.trace)}   t {w.cycle * 5}-{(w.cycle + 1) * 5} s   {w.phase}\n\n", "h")
        put("1 OBSERVE\n", "h")
        put(f"  background  primary {d['primary_background_mbps']:5.2f}  alternate {d['alternate_background_mbps']:5.2f} Mb/s\n")
        put(f"  elephant    {d['elephant_mbps']:5.2f} Mb/s   queues {w.paths[0].queue_before:.2f} / {w.paths[1].queue_before:.2f} Mbit\n")
        put("  primary if unchanged   ")
        put(f"{w.primary_load_pct:5.1f}%", "r" if w.primary_load_pct > 100 else "g")
        put("   (limit 100%)\n", "d")
        put("  alternate if moved     ")
        put(f"{w.alternate_load_pct:5.1f}%", "r" if w.alternate_load_pct > 90 else "g")
        put("   (limit  90%)\n", "d")
        put(f"2 DECIDE  [{ctrl}]\n", "h")
        put(f"  {CONTROLLER_RULE[ctrl]}\n", "d")
        req = w.requested
        tag = {"no_op": "g", "reroute": "c", "rate_limit": "a"}[req.action]
        param = f" {req.rate_limit_kbps} kbps" if req.action == "rate_limit" else " -> port 3" if req.action == "reroute" else ""
        put("  -> ", "g"); put(f"{req.action.upper()}{param}\n", tag)
        if ctrl == "A4":
            self.render_memory(w, put)
        put("3 GUARD  (independent safety check)\n", "h")
        put("  PASS  " if w.guard_allowed else "  VETO  ", "g" if w.guard_allowed else "r")
        put(f"{w.guard_reason}\n", "d")
        put("4 INSTALL  (simulated OpenFlow rule on s1)\n", "h")
        inst = w.installed
        if inst.action == "no_op":
            put("  no intervention rule; default forwarding\n", "d")
        else:
            act = "output:3" if inst.action == "reroute" else f"meter:{inst.rate_limit_kbps}kbps,output:2"
            put(f"  prio=100 in_port=1,ip,nw_dst=10.0.0.8\n  actions={act}  hard_timeout=5s\n",
                "c" if inst.action == "reroute" else "a")
        put("  prio=0   * actions=NORMAL\n", "d")
        put("5 OUTCOME  (fluid model, this window)\n", "h")
        put(f"  delay {w.latency_ms:5.1f} ms   loss {w.loss_pct:5.1f}%   goodput {w.throughput_kbps / 1000:5.2f} Mb/s\n")
        put(f"  doing nothing instead: delay {w.noop_latency_ms:5.1f} ms, loss {w.noop_loss_pct:5.1f}%\n", "d")
        kept = (w.noop_dropped_mbit - w.dropped_mbit) * PACKETS_PER_MBIT
        put("  packets kept vs doing nothing: ")
        put(f"{kept:+,.0f}", "g" if kept >= 0 else "r")
        put(f"   reward {w.reward:+.4f}\n")
        T.config(state=tk.DISABLED)

    def render_memory(self, w, put):
        n = len(self.session.memory.all_records())
        if w.requested.action != "rate_limit":
            put(f"  memory ({n} episodes) only tunes meters: idle\n", "d")
            return
        explore = "exploration" in w.requested.rationale
        chosen = re.search(r"(\d\.\d) Mbps headroom", w.requested.rationale)
        chosen = float(chosen.group(1)) if chosen else None
        put(f"  MEMORY {n} episodes (3 similar needed per option)\n", "h")
        for h in HEADROOMS:
            s = w.memory_scores.get(h)
            mark = "  <-" if chosen is not None and abs(h - chosen) < 1e-9 else ""
            if s:
                put(f"   headroom {h:.1f}  n={s['support']}  mean {s['mean']:+.4f}  low {s['lower']:+.4f}{mark}\n", "a" if mark else "g")
            else:
                put(f"   headroom {h:.1f}  n=0  untried{mark}\n", "a" if mark else "d")
        put("  mode: ", "g")
        put("EXPLORING (not enough evidence)\n" if explore else "USING EVIDENCE (best lower bound)\n", "a" if explore else "c")

    def write_log(self, w):
        act = w.installed.action
        param = f"{w.installed.rate_limit_kbps:5d}kbps" if act == "rate_limit" else "port 3   " if act == "reroute" else "         "
        line = (f" W{w.cycle + 1:03d} {w.cycle * 5:4d}s {w.phase[:14]:<14} P{w.primary_load_pct:4.0f}% A{w.alternate_load_pct:4.0f}%"
                f"  {act.upper():<10} {param}  dly {w.latency_ms:5.1f}ms  loss {w.loss_pct:5.1f}%  rwd {w.reward:+.4f}"
                + ("  VETO" if not w.guard_allowed else ""))
        self.log.insert(tk.END, line)
        self.log.itemconfig(tk.END, fg=RED if not w.guard_allowed else {"no_op": FAINT, "reroute": CYAN, "rate_limit": AMBER}[act])
        self.log.see(tk.END)

    # ------------------------------------------------------------- scopes
    def draw_scopes(self):
        if not hasattr(self, "session"):
            return
        h, z, n = self.session.history, self.shadow.history, len(self.session.trace)
        cum, a, b = [], 0.0, 0.0
        for x, y in zip(h, z):
            a += x.dropped_mbit; b += y.dropped_mbit
            cum.append((b - a) * PACKETS_PER_MBIT)
        span = max([1000.0] + [abs(v) for v in cum])
        series = {
            "delay": ([w.latency_ms for w in h], [w.latency_ms for w in z], 0, 60, (0, 20, 40, 60)),
            "loss": ([w.loss_pct for w in h], [w.loss_pct for w in z], 0, 50, (0, 25, 50)),
            "saved": (cum, None, -span * 1.1, span * 1.1, (0,)),
        }
        for key, (ours, base, lo, hi, ticks) in series.items():
            c = self.scopes[key]
            c.delete("all")
            W, H = c.winfo_width(), c.winfo_height()
            if W < 10:
                continue
            left, right, top, bottom = self.p(48), W - self.p(8), self.p(20), H - self.p(16)
            X = lambda i: left + (right - left) * i / max(1, n - 1)
            Y = lambda v: bottom - (bottom - top) * (min(max(v, lo), hi) - lo) / (hi - lo)
            for gx in range(0, n + 1, 20):
                c.create_line(X(min(gx, n - 1)), top, X(min(gx, n - 1)), bottom, fill=GRID)
            for t in ticks:
                c.create_line(left, Y(t), right, Y(t), fill=GRID if t else DIMG)
                c.create_text(left - self.p(4), Y(t), text=f"{t:g}", anchor="e", fill=FAINT, font=self.mono_small)
            if key == "saved":
                compact = lambda v: f"{v / 1000:+.1f}k"
                c.create_text(left - self.p(4), top, text=compact(hi), anchor="e", fill=FAINT, font=self.mono_small)
                c.create_text(left - self.p(4), bottom, text=compact(lo), anchor="e", fill=FAINT, font=self.mono_small)
            c.create_text(right, bottom + self.p(9), text="window ->", anchor="e", fill=FAINT, font=self.mono_small)
            for data, color, width in ((base, AMBER, 1), (ours, GREEN, 2)):
                if data and len(data) > 1:
                    c.create_line(*[v for i, y in enumerate(data) for v in (X(i), Y(y))], fill=color, width=self.p(width))
                elif data:
                    c.create_rectangle(X(0) - 1, Y(data[0]) - 1, X(0) + 1, Y(data[0]) + 1, outline=color)
            ctrl = self.session.controller
            if base is not None:
                c.create_line(left + self.p(4), self.p(9), left + self.p(18), self.p(9), fill=GREEN, width=self.p(2))
                c.create_text(left + self.p(22), self.p(9), anchor="w", fill=PALE, font=self.mono_small,
                              text=f"{ctrl} {ours[-1]:.1f}" if ours else ctrl)
                c.create_line(left + self.p(92), self.p(9), left + self.p(106), self.p(9), fill=AMBER, width=self.p(1))
                c.create_text(left + self.p(110), self.p(9), anchor="w", fill=PALE, font=self.mono_small,
                              text=f"A0 {base[-1]:.1f}" if base else "A0 (no control)")
            else:
                value = cum[-1] if cum else 0
                c.create_text(left + self.p(4), self.p(9), anchor="w", fill=GREEN if value >= 0 else RED, font=self.mono,
                              text=f"{value:+,.0f} packets  ({ctrl} vs A0)")

    def update_status(self, message):
        s = self.session
        h, z = s.history, self.shadow.history
        saved = (sum(w.dropped_mbit for w in z) - sum(w.dropped_mbit for w in h)) * PACKETS_PER_MBIT
        mem = f"Memory: {len(s.memory.all_records())} episodes" if s.controller == "A4" else "Memory: off"
        vetoes = sum(not w.guard_allowed for w in h)
        for cell, text in zip(self.status, (f"Window {s.cycle:03d}/{len(s.trace)}", f"Sim time {s.cycle * 5} s",
                                            f"{s.controller} vs A0 on {s.scenario}/{s.seed}", f"Saved {saved:+,.0f} packets",
                                            f"{mem}  Vetoes {vetoes}")):
            cell.config(text=text)
        self.status_msg.config(text=message)

    # ------------------------------------------------------------- misc
    def export(self):
        h = self.session.history
        if not h:
            messagebox.showinfo("Export", "Run or step at least one window first.")
            return
        s = self.session
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"selfx_{s.controller}_{s.scenario}_{s.seed}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            out = csv.writer(handle)
            out.writerow(["window", "phase", "primary_bg_mbps", "alternate_bg_mbps", "elephant_mbps", "requested", "installed",
                          "rate_limit_kbps", "guard_allowed", "delay_ms", "loss_pct", "goodput_kbps", "dropped_mbit",
                          "noop_delay_ms", "noop_loss_pct", "reward", "a0_delay_ms", "a0_loss_pct", "a0_dropped_mbit"])
            for w, a0 in zip(h, self.shadow.history):
                d = w.demand
                out.writerow([w.cycle, w.phase, d["primary_background_mbps"], d["alternate_background_mbps"], d["elephant_mbps"],
                              w.requested.action, w.installed.action, w.installed.rate_limit_kbps or "", w.guard_allowed,
                              w.latency_ms, w.loss_pct, w.throughput_kbps, w.dropped_mbit, w.noop_latency_ms, w.noop_loss_pct,
                              round(w.reward, 8), a0.latency_ms, a0.loss_pct, a0.dropped_mbit])
        self.update_status(f"Exported {len(h)} windows to {path}")

    def help(self):
        top = tk.Toplevel(self.root, bg=GREY)
        top.title("What am I looking at?")
        well = self.bevel(top)
        well.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        text = tk.Text(well, bg=HILITE, fg=INKC, font=self.mono, width=74, height=34, bd=0, padx=8, pady=6, wrap=tk.WORD)
        text.insert("1.0", HELP_TEXT)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)
        tk.Button(top, text="OK", width=10, command=top.destroy, bg=GREY, relief=tk.RAISED, bd=2).pack(pady=(0, 6))


def main():
    try:  # crisp text on high-DPI Windows displays
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    Console(root)
    root.mainloop()


if __name__ == "__main__":
    main()

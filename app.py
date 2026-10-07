"""PokeFT8 desktop demonstration: real Red ROM, simulated or receive-only UDP."""

import argparse
import datetime as dt
import socket
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from demo import real_sequence as sequence
from engine import Dex, Engine, band
from protocol import decode
from rom import ROOT, Red

BG = "#10151b"
PANEL = "#1b242d"
INK = "#e8eee9"
MUTED = "#92a49c"
GREEN = "#b6e58b"
RED = "#ed6b62"


class App:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.socket = None
        self.mode = "demo"
        self.closed = False
        self.started = time.monotonic()
        self.last_pump = time.monotonic()
        self.frame_budget = 0.0
        self.last_render = 0.0
        self.timeline = []
        self.index = 0
        self.last_rows = None
        self.packet_count = 0
        self.bad_packets = 0
        self.messages = []
        self.connection_error = ""
        self.red = Red(args.rom, clock=self.session_clock)
        self.root.title("PokéFT8 — Pokémon Red × amateur radio")
        self.root.configure(bg=BG)
        self.root.geometry("1120x810")
        self.root.minsize(1040, 770)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=PANEL,
            foreground=INK,
            fieldbackground=PANEL,
            borderwidth=0,
            rowheight=28,
            font=("Consolas", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#293640",
            foreground=INK,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#435a48")])
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=24, pady=(20, 12))
        tk.Label(top, text="PokéFT8", font=("Segoe UI", 29, "bold"), fg=INK, bg=BG).pack(
            side="left"
        )
        tk.Label(
            top,
            text="  POKÉMON RED  /  QSO BATTLES",
            font=("Consolas", 12),
            fg=MUTED,
            bg=BG,
        ).pack(side="left", padx=14)
        self.badge = tk.Label(
            top,
            text="DEMO • NO RF",
            font=("Consolas", 11, "bold"),
            fg=BG,
            bg=GREEN,
            padx=12,
            pady=7,
        )
        self.badge.pack(side="right")
        controls = tk.Frame(root, bg=BG)
        controls.pack(fill="x", padx=24, pady=(0, 12))
        for text, fn in [
            ("▶ Restart demo", self.start_demo),
            ("Ⅱ Pause", self.toggle_pause),
            ("Listen to WSJT-X", self.listen),
            ("Save frame", self.save_frame),
        ]:
            tk.Button(
                controls,
                text=text,
                command=fn,
                fg=INK,
                bg=PANEL,
                activebackground="#354734",
                activeforeground=INK,
                relief="flat",
                padx=15,
                pady=8,
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(0, 8))
        self.sound_button = tk.Button(
            controls,
            text="Sound: Off",
            command=self.toggle_sound,
            fg=INK,
            bg=PANEL,
            relief="flat",
            padx=12,
            pady=8,
            font=("Segoe UI", 10),
        )
        self.sound_button.pack(side="left", padx=(0, 8))
        self.paused = False
        self.transport = tk.Label(controls, text="", fg=MUTED, bg=BG, font=("Consolas", 10))
        self.transport.pack(side="right")
        middle = tk.Frame(root, bg=BG)
        middle.pack(fill="both", expand=True, padx=24)
        left = tk.Frame(middle, bg=PANEL, padx=16, pady=14)
        left.pack(side="left", fill="both")
        self.scene_title = tk.Label(
            left,
            text="ROUTE 1 • CALLING CQ",
            font=("Consolas", 12, "bold"),
            fg=GREEN,
            bg=PANEL,
        )
        self.scene_title.pack(anchor="w", pady=(0, 10))
        self.screen = tk.Label(left, bg="#081008", borderwidth=0)
        self.screen.pack()
        self.game_note = tk.Label(
            left,
            text="Real ROM frames • QSO-directed battle rules • audio muted",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        )
        self.game_note.pack(anchor="w", pady=(10, 0))
        right = tk.Frame(middle, bg=BG, padx=20)
        right.pack(side="left", fill="both", expand=True)
        self.call = tk.Label(right, text="CQ CQ CQ", font=("Consolas", 27, "bold"), fg=INK, bg=BG)
        self.call.pack(anchor="w")
        self.stage = tk.Label(
            right,
            text="",
            font=("Segoe UI", 12),
            fg=GREEN,
            bg=BG,
            wraplength=470,
            justify="left",
        )
        self.stage.pack(anchor="w", pady=(4, 12))
        self.rx = tk.Label(
            right,
            text="",
            font=("Consolas", 12),
            fg=INK,
            bg=PANEL,
            padx=12,
            pady=12,
            anchor="w",
            wraplength=440,
            justify="left",
        )
        self.rx.pack(fill="x")
        self.table_label(right, "REPLY FIELD · strongest directed reply wins")
        self.candidates = ttk.Treeview(right, columns=("call", "snr"), show="headings", height=3)
        for col, title, width in [("call", "STATION", 270), ("snr", "SNR", 130)]:
            self.candidates.heading(col, text=title)
            self.candidates.column(col, width=width)
        self.candidates.pack(fill="x")
        self.table_label(right, "CALLSIGN POKÉDEX · logged contacts")
        self.dex_table = ttk.Treeview(
            right, columns=("call", "band", "grid"), show="headings", height=4
        )
        for col, width in [("call", 190), ("band", 80), ("grid", 100)]:
            self.dex_table.heading(col, text=col.upper())
            self.dex_table.column(col, width=width)
        self.dex_table.pack(fill="x")
        self.dex_caption = tk.Label(
            right, text="", fg=MUTED, bg=BG, font=("Segoe UI", 9), anchor="w"
        )
        self.dex_caption.pack(fill="x", pady=(5, 10))
        self.feed = tk.Label(
            right,
            text="",
            font=("Consolas", 10),
            fg=MUTED,
            bg=BG,
            justify="left",
            anchor="nw",
            wraplength=450,
        )
        self.feed.pack(fill="both", expand=True)
        self.footer = tk.Label(
            root,
            text="",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 10),
            anchor="w",
            padx=24,
            pady=14,
        )
        self.footer.pack(fill="x")
        self.start_demo()
        self.root.after(25, self.pump)

    def table_label(self, parent, text):
        tk.Label(parent, text=text, fg=MUTED, bg=BG, font=("Consolas", 10, "bold")).pack(
            anchor="w", pady=(18, 7)
        )

    def new_engine(self, path):
        if hasattr(self, "engine"):
            self.engine.dex.db.close()
        self.engine = Engine(Dex(path), clock=self.session_clock)
        self.last_rows = None
        self.packet_count = self.bad_packets = 0
        self.messages = []
        self.red.action({"type": "reset"})

    def session_clock(self):
        if self.mode == "demo":
            return (self.paused_at if self.paused else time.monotonic()) - self.started
        return time.monotonic()

    def start_demo(self):
        if self.socket:
            self.socket.close()
            self.socket = None
        # The staged session always uses an in-memory dex. Real log is untouched.
        self.mode = "demo"
        self.new_engine(":memory:")
        self.timeline = sequence()
        self.index = 0
        self.started = time.monotonic()
        self.paused = False
        self.badge.configure(text="DEMO • NO RF", bg=GREEN)

    def toggle_sound(self):
        try:
            self.red.audio.enable(not self.red.audio.enabled)
        except RuntimeError as exc:
            self.messages.append(str(exc))
        self.sound_button.configure(text="Sound: On" if self.red.audio.enabled else "Sound: Off")

    def toggle_pause(self):
        if self.mode != "demo":
            self.footer.configure(
                text="Pause is available in demo mode; live telemetry continues to be received."
            )
            return
        self.paused = not self.paused
        if self.paused:
            self.red.audio.clear()
            self.paused_at = time.monotonic()
        else:
            self.started += time.monotonic() - self.paused_at

    def listen(self):
        if self.socket is not None:
            return
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            listener.bind(("127.0.0.1", self.args.port))
            listener.setblocking(False)
        except OSError as exc:
            listener.close()
            self.connection_error = f"Cannot listen on UDP {self.args.port}: {exc}"
            return
        if self.socket:
            self.socket.close()
        self.socket = listener
        self.connection_error = ""
        self.mode = "live"
        self.paused = False
        self.new_engine(str(ROOT / "data/contacts.sqlite3"))
        self.badge.configure(text="LIVE • RECEIVE ONLY", bg=RED)

    def ingest(self, packet):
        try:
            self.engine.handle(decode(packet))
            self.packet_count += 1
        except (ValueError, UnicodeError, OverflowError, KeyError):
            self.bad_packets += 1

    def pump(self):
        if self.closed:
            return
        current = time.monotonic()
        frame_elapsed = min(0.25, current - self.last_pump)
        self.last_pump = current
        if not self.paused:
            if self.mode == "demo":
                elapsed = time.monotonic() - self.started
                while self.index < len(self.timeline) and self.timeline[self.index][0] <= elapsed:
                    self.ingest(self.timeline[self.index][1])
                    self.index += 1
            elif self.socket:
                for _ in range(200):
                    try:
                        packet, _ = self.socket.recvfrom(65535)
                    except BlockingIOError:
                        break
                    self.ingest(packet)
            self.engine.poll()
            while self.engine.actions:
                action = self.engine.actions.pop(0)
                self.red.action(action)
                if action["type"] == "encounter":
                    signal = (
                        "SNR unknown" if action.get("snr") is None else f"{action['snr']:+d} dB"
                    )
                    self.messages.append(f"ENCOUNTER  {action['call']}  {signal}")
                if action["type"] == "attack":
                    self.messages.append(
                        f"{action.get('side', 'rx').upper()} {'MISS' if action.get('missed') else 'MOVE'}  {action['message']}"
                    )
                if action["type"] == "success":
                    self.messages.append(f"LOGGED     {action['call']} added to Pokédex")
            # Game Boy hardware runs at ~59.7275 Hz, independent of Tk redraw cost.
            self.frame_budget += frame_elapsed * (4194304 / 70224)
            frames = int(self.frame_budget)
            self.frame_budget -= frames
            self.red.tick(frames)
        else:
            self.frame_budget = 0.0
        if current - self.last_render >= 1 / 30:
            self.render()
            self.last_render = current
        self.root.after(8, self.pump)

    def render(self):
        e = self.engine
        slot_time = self.session_clock() if self.mode == "demo" else time.time()
        remaining = 15 - slot_time % 15
        self.red.slot_fraction = (slot_time % 15) / 15
        stale = e.last_packet is None or self.session_clock() - e.last_packet > 45
        if stale:
            phase, detail = "RADIO STANDBY", "No fresh telemetry"
        elif e.state == "success":
            phase, detail = "CONTACT LOGGED", "Finishing battle"
        elif e.transmitting:
            phase = "TRANSMITTING"
            detail = (e.tx_message.split()[-1] if e.tx_message else "CQ") + f"  {remaining:04.1f}s"
        elif e.decoding:
            phase, detail = "DECODING", "Checking replies..."
        elif e.state == "await_log":
            phase, detail = "EXCHANGE COMPLETE", "Awaiting QSO log"
        else:
            phase, detail = "LISTENING", f"Next slot {remaining:04.1f}s"
        self.red.radio_phase, self.red.radio_detail = phase, detail
        self.photo = ImageTk.PhotoImage(
            self.red.image().resize((480, 432), Image.Resampling.NEAREST)
        )
        self.screen.configure(image=self.photo)
        title = {
            "idle": "ROUTE 1 • STANDBY",
            "cq": "ROUTE 1 • CALLING CQ",
            "battle": "TRAINER BATTLE",
            "await_log": "FINAL EXCHANGE • AWAITING LOG",
            "success": "CONTACT COMPLETE",
        }[e.state]
        self.scene_title.configure(text=title)
        self.call.configure(text=e.opponent or ("CQ CQ CQ" if e.state == "cq" else "READY"))
        self.stage.configure(text=f"{phase} · {detail}\n{e.note}")
        self.game_note.configure(
            text=f"{e.own or self.red.own}  vs  {e.opponent or chr(8212)}\nCallsign trainers and Pokémon · original sprites"
        )
        heard = "unknown" if e.rx_snr is None else f"{e.rx_snr:+d} dB"
        reported = "unknown" if e.tx_snr is None else f"{e.tx_snr:+d} dB (last report)"
        self.rx.configure(
            text=f"{e.last_message}\nYou hear them: {heard}\nThey hear you: {reported}\n{e.exchange_stage or chr(8212)}"
            + (" · retry" if e.retry else "")
            + f" · {band(e.frequency)}"
        )
        candidates = sorted(e.candidates.values(), key=lambda x: -x["snr"])
        self.candidates.delete(*self.candidates.get_children())
        for c in candidates:
            self.candidates.insert(
                "",
                "end",
                values=(
                    ("▸ " if c["call"] == e.opponent else "") + c["call"],
                    f"{c['snr']:+d} dB",
                ),
            )
        rows = e.dex.rows()
        if rows != self.last_rows:
            self.dex_table.delete(*self.dex_table.get_children())
            unique = {}
            for row in rows:
                unique.setdefault(row[0], row)
            for call, b, _, grid in unique.values():
                self.dex_table.insert("", "end", values=(call, b, grid))
            self.last_rows = rows
        self.dex_caption.configure(
            text=f"{len(set(r[0] for r in rows))} unique callsigns · {len(rows)} QSOs · "
            + ("demo log resets on replay" if self.mode == "demo" else "saved locally")
        )
        self.feed.configure(text="\n".join(self.messages[-6:]))
        elapsed = self.session_clock()
        progress = (
            "DEMO COMPLETE" if self.red.mode == "victory" else f"DEMO {int(elapsed):02d}s / ~130s"
        )
        self.transport.configure(
            text=("PAUSED" if self.paused else progress)
            if self.mode == "demo"
            else f"UDP 127.0.0.1:{self.args.port}"
        )
        self.footer.configure(
            text=self.red.error
            or self.connection_error
            or f"{self.packet_count} packets decoded · {self.bad_packets} rejected · "
            + (
                "Synthetic stations and contact. No packets sent to WSJT-X."
                if self.mode == "demo"
                else "First WSJT-X instance selected. Game selection never changes your radio target."
            )
        )

    def save_frame(self):
        path = ROOT / "data" / ("frame-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".png")
        self.red.image().resize((640, 576), Image.Resampling.NEAREST).save(path)
        self.messages.append("FRAME SAVED  " + path.name)

    def close(self):
        self.closed = True
        if self.socket:
            self.socket.close()
        self.engine.dex.db.close()
        self.red.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=ROOT / "Pokemon Red.gb")
    parser.add_argument("--port", type=int, default=2237)
    parser.add_argument("--live", action="store_true", help="Start listening to WSJT-X immediately")
    args = parser.parse_args()
    root = tk.Tk()
    try:
        app = App(root, args)
        if args.live:
            app.listen()
    except Exception as exc:
        messagebox.showerror(
            "PokéFT8 could not start",
            f"{exc}\n\nSee README.md for setup and the supported ROM.",
        )
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()

"""QSO-to-game state, independent of emulator timing and UI."""

import datetime as dt
import re
import sqlite3
import time

from ecology import choose_species, grid4


def signal_power(snr):
    """Game balance, not RF power: -24..0 dB maps to 6..30 HP, capped."""
    return 12 if snr is None else round(6 + max(0, min(24, snr + 24)))


def exchange(message):
    token = message.upper().split()[-1]
    report = re.fullmatch(r"(R?)([+-][0-9]{2})", token)
    if report and -50 <= int(report[2]) <= 49:
        return ("roger-report" if report[1] else "report"), int(report[2])
    if token in ("RRR", "RR73", "73"):
        return token, None
    if re.fullmatch(r"[A-R]{2}[0-9]{2}", token):
        return "grid", None
    return "other", None


def band(freq):
    for low, high, name in [
        (1800000, 2000000, "160m"),
        (3500000, 4000000, "80m"),
        (5300000, 5500000, "60m"),
        (7000000, 7300000, "40m"),
        (10100000, 10150000, "30m"),
        (14000000, 14350000, "20m"),
        (18068000, 18168000, "17m"),
        (21000000, 21450000, "15m"),
        (24890000, 24990000, "12m"),
        (28000000, 29700000, "10m"),
        (50000000, 54000000, "6m"),
    ]:
        if low <= freq <= high:
            return name
    return str(freq)


class Dex:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, call TEXT, band TEXT, ended TEXT, grid TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS habitats (grid TEXT PRIMARY KEY, species TEXT, rarity TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS captures (id TEXT PRIMARY KEY, call TEXT, band TEXT, ended TEXT, grid TEXT, species TEXT, rarity TEXT)"
        )

    def habitat(self, grid, call):
        grid = grid4(grid)
        if not grid:
            return choose_species("", call=call)
        row = self.db.execute(
            "SELECT species,rarity FROM habitats WHERE grid=?", (grid,)
        ).fetchone()
        if row:
            return row
        count = self.db.execute(
            "SELECT COUNT(*) FROM contacts WHERE substr(upper(grid),1,4)=?", (grid,)
        ).fetchone()[0]
        species, rarity = choose_species(grid, count)
        with self.db:
            self.db.execute("INSERT INTO habitats VALUES (?,?,?)", (grid, species, rarity))
        return species, rarity

    def capture(self, attempt, call, frequency, grid, species, rarity):
        with self.db:
            result = self.db.execute(
                "INSERT OR IGNORE INTO captures VALUES (?,?,?,?,?,?,?)",
                (
                    attempt,
                    call,
                    band(frequency),
                    dt.datetime.now(dt.timezone.utc).isoformat(),
                    grid,
                    species,
                    rarity,
                ),
            )
        return bool(result.rowcount)

    def collection(self):
        return self.db.execute(
            "SELECT call,band,ended,grid,species FROM captures ORDER BY ended DESC"
        ).fetchall()

    def add(self, e):
        # Both QSOLogged and LoggedADIF normalize to this identity, including repeat QSOs.
        end = dt.datetime.fromisoformat(e["end"]).replace(microsecond=0).isoformat()
        key = "|".join(
            [
                e["instance"],
                e["call"].upper(),
                band(e["frequency"]),
                e["mode"].upper(),
                end,
            ]
        )
        with self.db:
            c = self.db.execute(
                "INSERT OR IGNORE INTO contacts VALUES (?,?,?,?,?)",
                (key, e["call"].upper(), band(e["frequency"]), end, e.get("grid", "")),
            )
        return bool(c.rowcount)

    def rows(self):
        return self.db.execute(
            "SELECT call,band,ended,grid FROM contacts ORDER BY ended DESC"
        ).fetchall()


class Engine:
    def __init__(self, dex, clock=time.monotonic):
        self.dex, self.clock = dex, clock
        self.instance = None
        self.state = "idle"
        self.own = ""
        self.frequency = 0
        self.opponent = ""
        self.candidates = {}
        self.seen = set()
        self.actions = []
        self.attacks = 0
        self.deadline = None
        self.last_reply = None
        self.last_packet = None
        self.attempt_started = None
        self.last_message = "Ready for CQ"
        self.note = ""
        self.rx_snr = None
        self.tx_snr = None
        self.exchange_seen = set()
        self.exchange_stage = ""
        self.retry = False
        self.was_transmitting = False
        self.reply_expected = False
        self.reply_decoding = False
        self.decoding = False
        self.transmitting = False
        self.tx_message = ""
        self.selected_target = ""
        self.station_grids = {}
        self.station_snr = {}
        self.grid = ""
        self.species = "PIDGEY"
        self.rarity = "common"
        self.watts = 50
        self.progress = 0
        self.acks = set()
        self.has_report = False
        self.capture_awarded = False
        self.capture_due = None

    def emit(self, kind, **data):
        self.actions.append({"type": kind, **data})

    def cancel(self, reason="Encounter cancelled"):
        self.actions.clear()  # Never deliver queued moves from an abandoned partner.
        self.state = "idle"
        self.opponent = ""
        self.candidates.clear()
        self.rx_snr = self.tx_snr = None
        self.exchange_seen.clear()
        self.exchange_stage = ""
        self.retry = False
        self.deadline = None
        self.last_reply = None
        self.attempt_started = None
        self.attacks = 0
        self.note = reason
        self.reply_expected = False
        self.reply_decoding = False
        self.progress = 0
        self.acks.clear()
        self.has_report = False
        self.capture_awarded = False
        self.capture_due = None
        self.grid = ""
        self.emit("reset")

    def begin_partner(self, call, snr=None, reason="Calling station"):
        self.cancel(reason)
        self.opponent = call
        self.state = "battle"
        self.last_reply = self.clock()
        self.attempt_started = dt.datetime.now(dt.timezone.utc)
        self.note = f"{reason}: {call}"
        self.grid = self.station_grids.get(call, "")
        self.species, self.rarity = self.dex.habitat(self.grid, call)
        snr = self.station_snr.get(call) if snr is None else snr
        self.emit(
            "encounter",
            call=call,
            own=self.own,
            snr=snr,
            species=self.species,
            grid=self.grid,
            rarity=self.rarity,
            watts=self.watts,
        )

    def progress_message(self, message, side, not_before=0):
        stage, _ = exchange(message)
        self.progress = max(
            self.progress,
            {"grid": 1, "report": 2, "roger-report": 3, "RRR": 4, "RR73": 5, "73": 5}.get(stage, 0),
        )
        if stage in ("report", "roger-report"):
            self.has_report = True
        if stage in ("RRR", "RR73", "73"):
            self.acks.add((side, stage))
        complete = (
            ("rx", "RR73") in self.acks
            or (("tx", "RR73") in self.acks and self.tx_snr is not None)
            or (any(s == "RRR" for _, s in self.acks) and any(s == "73" for _, s in self.acks))
        )
        if complete and self.has_report:
            self.award_capture(not_before)

    def award_capture(self, not_before=0):
        if self.capture_awarded:
            return
        if not_before > self.clock():
            self.capture_due = not_before
            self.note = "Sending final acknowledgement — preparing Poke Ball"
            return
        self.capture_due = None
        self.capture_awarded = True
        attempt = "|".join(
            [self.instance, self.opponent, str(self.frequency), self.attempt_started.isoformat()]
        )
        self.dex.capture(
            attempt, self.opponent, self.frequency, self.grid, self.species, self.rarity
        )
        self.state = "success"
        self.reply_expected = False
        self.note = "QSO acknowledged — capturing!"
        self.emit("capture", call=self.opponent, not_before=not_before)

    @staticmethod
    def valid_call(call):
        return bool(
            re.fullmatch(r"[A-Z0-9/]+", call)
            and any(c.isdigit() for c in call)
            and any(c.isalpha() for c in call)
        )

    def finish_batch(self):
        if self.state != "cq" or not self.candidates:
            return
        winner = min(self.candidates.values(), key=lambda x: (-x["snr"], x["call"]))
        candidates = self.candidates.copy()
        self.begin_partner(winner["call"], winner["snr"], "Strongest directed reply")
        self.candidates = candidates
        self.note = f"Strongest directed reply: {winner['snr']:+d} dB"
        self.attack(winner["message"], winner["snr"])

    def attack(self, message, snr):
        known_grid = self.station_grids.get(self.opponent, "")
        if not self.grid and known_grid:
            self.grid = known_grid
            self.species, self.rarity = self.dex.habitat(self.grid, self.opponent)
            self.emit(
                "identity",
                call=self.opponent,
                own=self.own,
                snr=snr,
                watts=self.watts,
                species=self.species,
                grid=self.grid,
                rarity=self.rarity,
            )
        self.rx_snr = snr
        stage, report = exchange(message)
        if report is not None:
            self.tx_snr = report
        self.retry = stage in self.exchange_seen
        self.exchange_seen.add(stage)
        self.exchange_stage = stage
        self.reply_expected = False

        self.attacks += 1
        self.last_reply = self.clock()
        self.last_message = message
        self.emit(
            "attack",
            call=self.opponent,
            message=message,
            number=self.attacks,
            rx_snr=self.rx_snr,
            tx_snr=self.tx_snr,
            stage=stage,
            retry=self.retry,
            side="rx",
            move=message.split()[-1],
            damage=signal_power(self.rx_snr),
            snr=snr,
            target_hp={0: 100, 1: 80, 2: 55, 3: 25, 4: 10, 5: 5}[
                max(
                    self.progress,
                    {"grid": 1, "report": 2, "roger-report": 3, "RRR": 4, "RR73": 5, "73": 5}.get(
                        stage, 0
                    ),
                )
            ],
            not_before=self.clock() + 2,
        )
        if message.split()[-1] in ("RRR", "RR73", "73"):
            self.state = "await_log"
            self.note = "Final acknowledgement — awaiting completion"
        self.progress_message(message, "rx")

    def handle(self, e):
        now = self.clock()
        if self.instance is None and e["type"] == "status":
            self.instance = e["instance"]
        if e["instance"] != self.instance:
            return
        self.last_packet = now
        if e["type"] == "close":
            self.cancel("WSJT-X closed")
        elif e["type"] == "status":
            if e.get("mode") != "FT8" or e.get("special") not in (None, 0):
                self.cancel("Demo supports standard FT8 operation")
                return
            if self.frequency and e["frequency"] != self.frequency:
                self.cancel("Dial frequency changed")
            self.frequency = e["frequency"]
            self.own = e["own"].upper()
            tx = (e.get("tx_message") or "").upper()
            if (
                self.transmitting
                and not e["transmitting"]
                and self.capture_due is not None
                and now < self.capture_due - 0.5
            ):
                self.capture_due = None
                self.acks = {ack for ack in self.acks if ack not in (("tx", "RR73"), ("tx", "73"))}
                self.note = "Final transmission stopped early — capture deferred"
            self.transmitting = e["transmitting"]
            self.decoding = e["decoding"]
            self.tx_message = tx
            target = e.get("target", "").upper().strip()
            target_changed = target != self.selected_target
            self.selected_target = target
            if self.valid_call(target) and grid4(e.get("grid")):
                self.station_grids[target] = grid4(e["grid"])
            started_tx = e["transmitting"] and not self.was_transmitting
            self.was_transmitting = e["transmitting"]
            words = tx.split()
            directed = len(words) >= 3 and words[1] == self.own and self.valid_call(words[0])
            if e["transmitting"] and tx.startswith("CQ "):
                if self.state != "cq":
                    self.cancel("Calling CQ")
                    self.state = "cq"
                    self.attempt_started = dt.datetime.now(dt.timezone.utc)
                    self.attacks = 0
                    self.emit("cq", own=self.own)
                self.last_message = tx
            elif e["transmitting"] and directed:
                # The actual outgoing address wins over a stale DX-call field.
                if (words[0] != self.opponent and self.state != "idle") or (
                    self.state == "idle" and (started_tx or target_changed)
                ):
                    self.begin_partner(words[0])
                    started_tx = True
            elif (
                self.valid_call(target)
                and target_changed
                and (e.get("tx_enabled") or self.state in ("battle", "await_log"))
            ):
                if target != self.opponent:
                    self.begin_partner(target, reason="Selected station")
            elif (
                target_changed
                and not target
                and not e.get("tx_enabled")
                and self.state in ("battle", "await_log")
            ):
                self.cancel("QSO partner cleared")
            if (
                started_tx
                and self.opponent
                and self.state in ("battle", "await_log")
                and len(words) >= 3
                and words[:2] == [self.opponent, self.own]
            ):
                self.emit(
                    "attack",
                    side="tx",
                    call=self.own,
                    message=tx,
                    move=words[-1],
                    number=self.attacks,
                    damage=signal_power(self.tx_snr),
                    tx_snr=self.tx_snr,
                    not_before=now + 10.0,
                    target_hp={0: 100, 1: 80, 2: 55, 3: 25, 4: 10, 5: 5}[
                        max(
                            self.progress,
                            {
                                "grid": 1,
                                "report": 2,
                                "roger-report": 3,
                                "RRR": 4,
                                "RR73": 5,
                                "73": 5,
                            }.get(exchange(tx)[0], 0),
                        )
                    ],
                )
                self.reply_expected = words[-1] != "73"
                self.reply_decoding = False
                self.last_message = tx
                self.progress_message(tx, "tx", now + 13.2)
            if self.reply_expected and not e["transmitting"]:
                if e["decoding"]:
                    self.reply_decoding = True
                elif self.reply_decoding:
                    self.emit(
                        "attack",
                        side="rx",
                        call=self.opponent,
                        move="MISS",
                        message="No partner reply decoded (inferred miss)",
                        number=self.attacks,
                        damage=0,
                        missed=True,
                    )
                    self.reply_expected = self.reply_decoding = False
            if self.state == "cq" and not e["decoding"]:
                self.finish_batch()
        elif e["type"] == "decode":
            if (
                not e.get("new")
                or e.get("off_air")
                or e.get("low_confidence")
                or e.get("mode") not in ("~", "FT8")
            ):
                return
            words = e["message"].upper().split()
            if len(words) >= 3:
                sender = words[-2] if words[0] == "CQ" else words[1]
                sender = sender if self.valid_call(sender) else ""
                if sender:
                    self.station_snr[sender] = e["snr"]
                    if exchange(e["message"])[0] == "grid":
                        self.station_grids[sender] = grid4(words[-1])
            if (
                len(words) < 3
                or words[0] != self.own
                or not re.fullmatch(r"[A-Z0-9/]+", words[1])
                or not any(c.isdigit() for c in words[1])
            ):
                return
            # Duplicate packets in one slot do not attack twice; a real retry next slot does.
            day = dt.datetime.now(dt.timezone.utc).date().isoformat()
            key = (day, e["time_ms"] // 15000, words[1], self.frequency)
            if key in self.seen:
                return
            self.seen.add(key)
            if len(self.seen) > 5000:
                self.seen = {key}
            call = words[1]
            if self.state == "cq":
                old = self.candidates.get(call)
                if old is None or e["snr"] > old["snr"]:
                    self.candidates[call] = {
                        "call": call,
                        "snr": e["snr"],
                        "message": e["message"],
                    }
                # Fallback for bridges missing end-of-decoding status; use a quiet gap.
                self.deadline = now + 2
            elif self.state in ("battle", "await_log") and call == self.opponent:
                self.attack(e["message"], e["snr"])
        elif e["type"] == "logged":
            ended = dt.datetime.fromisoformat(e["end"])
            if ended.tzinfo is None or self.attempt_started is None:
                return
            if (
                not self.attempt_started - dt.timedelta(seconds=60)
                <= ended
                <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)
            ):
                return
            if (
                self.state in ("battle", "await_log", "success")
                and e["call"].upper() == self.opponent
                and e["mode"].upper() == "FT8"
                and band(e["frequency"]) == band(self.frequency)
            ):
                if self.dex.add(e):
                    self.award_capture()
                    self.note = "Captured — also confirmed by WSJT-X log"

    def poll(self):
        now = self.clock()
        if self.capture_due is not None and now >= self.capture_due and not self.transmitting:
            self.award_capture()
        if self.deadline is not None and now >= self.deadline:
            self.finish_batch()
        if (
            self.state in ("battle", "await_log")
            and self.last_reply is not None
            and now - self.last_reply > 180
        ):
            self.cancel("No QSO reply for three minutes")
        if self.state == "cq" and self.last_packet is not None and now - self.last_packet > 45:
            self.cancel("Telemetry disconnected")

"""Receive-only WSJT-X QDataStream decoder and binary demo packet generator.

Wire reference: WSJTX/wsjtx Network/NetworkMessage.hpp, schema 2/3.
No Reply, Configure, FreeText or other radio control messages are emitted.
"""

import datetime as dt
import re
import struct

MAGIC = 0xADBCCBDA


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def get(self, fmt):
        size = struct.calcsize(">" + fmt)
        if self.pos + size > len(self.data):
            raise ValueError("Truncated WSJT-X packet")
        result = struct.unpack_from(">" + fmt, self.data, self.pos)[0]
        self.pos += size
        return result

    def text(self):
        length = self.get("I")
        if length == 0xFFFFFFFF:
            return ""
        if length > 65507 or self.pos + length > len(self.data):
            raise ValueError("Invalid string length")
        result = self.data[self.pos : self.pos + length].decode("utf-8")
        self.pos += length
        return result

    def optional(self, method, default=None):
        return method() if self.pos < len(self.data) else default

    def datetime(self):
        day, millis, spec = self.get("q"), self.get("I"), self.get("B")
        offset = self.get("i") if spec == 2 else 0
        if spec not in (0, 1, 2):
            raise ValueError("Unsupported QDateTime timezone")
        value = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(
            days=day - 2440588, milliseconds=millis, seconds=-offset
        )
        return value.isoformat()


def adif_fields(text):
    fields = {}
    for match in re.finditer(r"<([A-Za-z0-9_]+):(\d+)(?::[A-Za-z])?>", text):
        fields[match[1].upper()] = text[match.end() : match.end() + int(match[2])]
    return fields


def decode(data):
    r = Reader(data)
    if r.get("I") != MAGIC:
        raise ValueError("Not a WSJT-X datagram")
    schema, kind = r.get("I"), r.get("I")
    if schema not in (2, 3):
        raise ValueError("Unsupported schema")
    e = {"instance": r.text(), "schema": schema}
    if kind == 0:
        return e | {"type": "heartbeat"}
    if kind == 1:
        e.update(
            type="status",
            frequency=r.get("Q"),
            mode=r.text(),
            target=r.text(),
            report=r.text(),
            tx_mode=r.text(),
            tx_enabled=r.get("?"),
            transmitting=r.get("?"),
            decoding=r.get("?"),
            rx_df=r.get("I"),
            tx_df=r.get("I"),
            own=r.text(),
            own_grid=r.text(),
            grid=r.text(),
        )
        # Fields are appended over time; older schemas/versions can omit them.
        for name, method in [
            ("watchdog", lambda: r.get("?")),
            ("submode", r.text),
            ("fast", lambda: r.get("?")),
            ("special", lambda: r.get("B")),
            ("tolerance", lambda: r.get("I")),
            ("period", lambda: r.get("I")),
            ("configuration", r.text),
            ("tx_message", r.text),
        ]:
            e[name] = r.optional(method)
    elif kind == 2:
        e.update(
            type="decode",
            new=r.get("?"),
            time_ms=r.get("I"),
            snr=r.get("i"),
            dt=r.get("d"),
            df=r.get("I"),
            mode=r.text(),
            message=r.text(),
        )
        e["low_confidence"] = r.optional(lambda: r.get("?"), False)
        e["off_air"] = r.optional(lambda: r.get("?"), False)
    elif kind == 5:
        e.update(
            type="logged",
            end=r.datetime(),
            call=r.text(),
            grid=r.text(),
            frequency=r.get("Q"),
            mode=r.text(),
            sent=r.text(),
            received=r.text(),
        )
    elif kind == 12:
        f = adif_fields(r.text())
        date = f.get("QSO_DATE_OFF", f.get("QSO_DATE", ""))
        time = f.get("TIME_OFF", f.get("TIME_ON", "")).ljust(6, "0")
        end = dt.datetime.strptime(date + time, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
        e.update(
            type="logged",
            call=f.get("CALL", ""),
            grid=f.get("GRIDSQUARE", ""),
            frequency=round(float(f.get("FREQ", "0")) * 1_000_000),
            mode=f.get("MODE", ""),
            end=end.isoformat(),
        )
    elif kind == 6:
        e["type"] = "close"
    else:
        e["type"] = "ignored"
    return e


def string(value):
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def header(kind, instance="PokeFT8-DEMO"):
    return struct.pack(">III", MAGIC, 3, kind) + string(instance)


def status(tx_message="", transmitting=False, decoding=False, target=""):
    return (
        header(1)
        + struct.pack(">Q", 14074000)
        + string("FT8")
        + string(target)
        + string("-07")
        + string("FT8")
        + struct.pack(">???II", True, transmitting, decoding, 1500, 1500)
        + string("N0CALL")
        + string("CN79")
        + string("")
        + struct.pack(">?", False)
        + string("")
        + struct.pack(">?BII", False, 0, 50, 15)
        + string("Demo")
        + string(tx_message)
    )


def reception(message, snr, slot):
    return (
        header(2)
        + struct.pack(">?IidI", True, slot * 15000, snr, 0.1, 1500)
        + string("~")
        + string(message)
        + struct.pack(">??", False, False)
    )


def logged(call, end):
    fields = {
        "CALL": call,
        "MODE": "FT8",
        "FREQ": "14.0755",
        "GRIDSQUARE": "PM95",
        "QSO_DATE": end.strftime("%Y%m%d"),
        "TIME_OFF": end.strftime("%H%M%S"),
    }
    return header(12) + string("".join(f"<{k}:{len(v)}>{v}" for k, v in fields.items()) + "<EOR>")

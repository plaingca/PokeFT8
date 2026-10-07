import datetime as dt
import socket
import struct
import tempfile
import unittest
from pathlib import Path

import protocol as wire
from demo import sequence
from engine import Dex, Engine, exchange, signal_power


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.dex = Dex(":memory:")
        self.e = Engine(self.dex)

    def tearDown(self):
        self.dex.db.close()

    def feed(self, packet):
        self.e.handle(wire.decode(packet))

    def test_directional_reports_and_retry(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        first = self.e.actions[-1]
        self.assertIsNone(first["tx_snr"])
        self.assertEqual(first["rx_snr"], -5)
        self.feed(wire.reception("N0CALL JA1ABC R-19", -3, 3))
        attack = self.e.actions[-1]
        self.assertEqual((attack["tx_snr"], attack["rx_snr"]), (-19, -3))
        self.assertEqual(attack["side"], "rx")
        self.assertEqual(attack["damage"], signal_power(-3))
        self.feed(wire.reception("N0CALL JA1ABC R-19", -12, 5))
        retry = self.e.actions[-1]
        self.assertTrue(retry["retry"])
        self.assertEqual(retry["damage"], signal_power(-12))
        self.feed(wire.reception("N0CALL JA1ABC RR73", -15, 7))
        self.assertEqual(self.e.tx_snr, -19)
        self.assertEqual(self.e.rx_snr, -15)
        self.e.cancel()
        self.assertIsNone(self.e.tx_snr)
        self.assertIsNone(self.e.rx_snr)

    def test_report_variants_and_power_bounds(self):
        self.assertEqual(exchange("N0CALL JA1ABC +05"), ("report", 5))
        self.assertEqual(exchange("N0CALL JA1ABC R-07"), ("roger-report", -7))
        self.assertEqual(exchange("N0CALL JA1ABC PM95"), ("grid", None))
        self.assertEqual(exchange("N0CALL JA1ABC RR73"), ("RR73", None))
        self.assertEqual(exchange("N0CALL JA1ABC -99"), ("other", None))
        self.assertEqual(signal_power(-50), 6)
        self.assertEqual(signal_power(49), 30)
        self.assertLess(signal_power(-20), signal_power(-5))

    def test_rrr_waits_for_log(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        self.feed(wire.reception("N0CALL JA1ABC RRR", -10, 3))
        self.assertEqual(self.e.state, "await_log")
        self.assertEqual(self.dex.rows(), [])

    def test_tx_edges_and_inferred_receive_miss(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        self.e.actions.clear()
        tx = wire.status("JA1ABC N0CALL -05", True, target="JA1ABC")
        self.feed(tx)
        self.feed(tx)
        self.assertEqual(len(self.e.actions), 1)
        self.assertEqual(self.e.actions[0]["side"], "tx")
        self.assertEqual(self.e.actions[0]["move"], "-05")
        self.feed(wire.status("", False, True))
        self.feed(wire.status("", False, False))
        self.assertTrue(self.e.actions[-1]["missed"])
        self.assertEqual(self.e.actions[-1]["damage"], 0)
        count = len(self.e.actions)
        self.feed(wire.status())
        self.assertEqual(len(self.e.actions), count)
        self.feed(tx)
        self.feed(wire.status("", False, True))
        self.feed(wire.reception("N0CALL JA1ABC R-07", -8, 9))
        count = len(self.e.actions)
        self.feed(wire.status())
        self.assertEqual(len(self.e.actions), count)

    def test_complete_binary_session(self):
        for _, packet in sequence():
            self.feed(packet)
        self.assertEqual(self.e.opponent, "JA1ABC")
        self.assertEqual(self.e.attacks, 4)
        self.assertEqual(self.e.state, "success")
        self.assertEqual(len(self.dex.rows()), 1)

    def test_call_station_without_cq(self):
        self.feed(wire.status("W1AW N0CALL CN79", True, target="W1AW"))
        self.assertEqual((self.e.state, self.e.opponent), ("battle", "W1AW"))
        self.assertIsNotNone(self.e.attempt_started)
        self.assertEqual([a["type"] for a in self.e.actions], ["reset", "encounter", "attack"])
        self.assertIsNone(self.e.actions[1]["snr"])
        count = len(self.e.actions)
        self.feed(wire.status("W1AW N0CALL CN79", True, target="W1AW"))
        self.assertEqual(len(self.e.actions), count)

    def test_selected_partner_switch_clears_old_actions(self):
        self.feed(wire.status("W1AW N0CALL CN79", True, target="W1AW"))
        self.feed(wire.reception("N0CALL W1AW R-15", -10, 1))
        self.feed(wire.status("", False, target="JA1ABC"))
        self.assertEqual(self.e.opponent, "JA1ABC")
        self.assertIsNone(self.e.tx_snr)
        self.assertEqual(self.e.attacks, 0)
        self.assertEqual([a["type"] for a in self.e.actions], ["reset", "encounter"])
        self.feed(wire.reception("N0CALL W1AW R-15", -5, 3))
        self.feed(wire.logged("W1AW", dt.datetime.now(dt.timezone.utc)))
        self.assertEqual(self.e.attacks, 0)
        self.assertEqual(self.dex.rows(), [])

    def test_actual_tx_overrides_stale_target(self):
        self.feed(wire.status("W1AW N0CALL CN79", True, target="W1AW"))
        self.feed(wire.status("JA1ABC N0CALL -05", True, target="W1AW"))
        self.assertEqual(self.e.opponent, "JA1ABC")
        self.assertEqual(self.e.actions[-1]["message"], "JA1ABC N0CALL -05")

    def test_return_to_cq_discards_partner(self):
        self.feed(wire.status("W1AW N0CALL CN79", True, target="W1AW"))
        self.feed(wire.status("CQ N0CALL CN79", True, target="W1AW"))
        self.assertEqual((self.e.state, self.e.opponent), ("cq", ""))
        self.assertEqual([a["type"] for a in self.e.actions], ["reset", "cq"])

    def test_timeout_stays_idle_until_new_tx_or_selection(self):
        now = [0.0]
        self.e.clock = lambda: now[0]
        tx = wire.status("W1AW N0CALL CN79", True, target="W1AW")
        self.feed(tx)
        now[0] = 181
        self.e.poll()
        self.feed(tx)
        self.assertEqual(self.e.state, "idle")
        self.feed(wire.status("", False, target="W1AW"))
        self.feed(tx)
        self.assertEqual(self.e.opponent, "W1AW")
        now[0] = 362
        self.e.poll()
        self.feed(wire.status("", False, target="JA1ABC"))
        self.assertEqual(self.e.opponent, "JA1ABC")

    def test_disabled_idle_selection_is_not_a_call(self):
        event = wire.decode(wire.status("", False, target="W1AW"))
        self.e.handle(event | {"tx_enabled": False})
        self.assertEqual(self.e.state, "idle")

    def test_strongest_after_batch_not_first_packet(self):
        self.feed(wire.status("CQ N0CALL CN79", True))
        self.feed(wire.reception("N0CALL W1AW FN31", -19, 1))
        self.assertEqual(self.e.state, "cq")
        self.feed(wire.reception("N0CALL JA1ABC PM95", -5, 1))
        self.feed(wire.status())
        self.assertEqual(self.e.opponent, "JA1ABC")

    def test_duplicate_slot_and_real_retry(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        p = wire.reception("N0CALL JA1ABC R-07", -5, 3)
        self.feed(p)
        self.feed(p)
        self.assertEqual(self.e.attacks, 2)
        self.feed(wire.reception("N0CALL JA1ABC R-07", -5, 5))
        self.assertEqual(self.e.attacks, 3)

    def test_other_stations_and_replay_do_not_attack(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        self.feed(wire.reception("N0CALL W1AW R-07", 2, 3))
        self.feed(wire.reception("W1AW JA1ABC R-07", 2, 3))
        e = wire.decode(wire.reception("N0CALL JA1ABC R-07", -4, 3))
        for field, value in [
            ("new", False),
            ("off_air", True),
            ("low_confidence", True),
        ]:
            self.e.handle(e | {field: value})
        self.assertEqual(self.e.attacks, 1)

    def test_no_log_no_reward(self):
        for t, p in sequence():
            if t < 42:
                self.feed(p)
        self.assertEqual(self.e.state, "await_log")
        self.assertEqual(self.dex.rows(), [])

    def test_wrong_call_or_band_not_logged(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        self.feed(wire.logged("W1AW", dt.datetime.now(dt.timezone.utc)))
        e = wire.decode(wire.logged("JA1ABC", dt.datetime.now(dt.timezone.utc)))
        self.e.handle(e | {"frequency": 7074000})
        self.assertEqual(self.dex.rows(), [])

    def test_other_instance_does_not_contaminate(self):
        self.feed(wire.status("CQ N0CALL CN79", True))
        event = wire.decode(wire.reception("N0CALL W1AW FN31", -1, 1))
        self.e.handle(event | {"instance": "other"})
        self.assertEqual(self.e.candidates, {})

    def test_all_truncations_rejected_without_crash(self):
        packet = wire.reception("N0CALL JA1ABC PM95", -5, 1)
        for length in range(len(packet) - 2):
            with self.assertRaises((ValueError, UnicodeError)):
                wire.decode(packet[:length])

    def test_schema_unknown_type_and_null(self):
        self.assertEqual(wire.decode(wire.header(200))["type"], "ignored")
        r = wire.Reader(struct.pack(">I", 0xFFFFFFFF))
        self.assertEqual(r.text(), "")
        with self.assertRaises(ValueError):
            wire.decode(b"not telemetry")

    def test_persistent_duplicate_logging(self):
        with tempfile.TemporaryDirectory() as folder:
            p = str(Path(folder) / "log.sqlite")
            d = Dex(p)
            event = wire.decode(wire.logged("JA1ABC", dt.datetime.now(dt.timezone.utc)))
            self.assertTrue(d.add(event))
            d.db.close()
            d = Dex(p)
            self.assertFalse(d.add(event))
            self.assertEqual(len(d.rows()), 1)
            d.db.close()

    def test_timeout(self):
        now = [0.0]
        self.e.clock = lambda: now[0]
        for _, p in sequence()[:6]:
            self.feed(p)
        now[0] = 181
        self.e.poll()
        self.assertEqual(self.e.state, "idle")
        self.assertEqual(self.dex.rows(), [])

    def test_stale_log_not_rewarded(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        self.feed(wire.logged("JA1ABC", dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)))
        self.assertEqual(self.dex.rows(), [])

    def test_qso_logged_and_adif_deduplicate(self):
        for _, p in sequence()[:6]:
            self.feed(p)
        end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        days = (end.date() - dt.date(1970, 1, 1)).days + 2440588
        millis = (end.hour * 3600 + end.minute * 60 + end.second) * 1000
        packet = (
            wire.header(5)
            + struct.pack(">qIB", days, millis, 1)
            + wire.string("JA1ABC")
            + wire.string("PM95")
            + struct.pack(">Q", 14075500)
            + wire.string("FT8")
            + wire.string("-05")
            + wire.string("-07")
        )
        event = wire.decode(packet)
        self.assertTrue(self.dex.add(event))
        self.assertFalse(self.dex.add(wire.decode(wire.logged("JA1ABC", end))))

    def test_udp_loopback_entire_session(self):
        with (
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender,
        ):
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            for _, packet in sequence():
                sender.sendto(packet, receiver.getsockname())
                self.feed(receiver.recv(65535))
        self.assertEqual(self.e.state, "success")
        self.assertEqual(len(self.dex.rows()), 1)


if __name__ == "__main__":
    unittest.main()

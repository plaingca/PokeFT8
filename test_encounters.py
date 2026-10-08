import string
import tempfile
import unittest
from pathlib import Path

import protocol as wire
from ecology import LEGENDARY, SPECIES, choose_species, grid4, snr_level, watts_level
from engine import Dex, Engine


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.dex = Dex(":memory:")
        self.e = Engine(self.dex)

    def tearDown(self):
        self.dex.db.close()

    def feed(self, packet):
        self.e.handle(wire.decode(packet))

    def begin(self):
        self.feed(wire.status("CQ N0CALL CN79", True))
        self.feed(wire.reception("N0CALL JA1ABC PM95", -20, 1))
        self.feed(wire.status())
        self.feed(wire.status("JA1ABC N0CALL -20", True, target="JA1ABC"))
        self.feed(wire.status("", False, target="JA1ABC"))

    def test_weak_signal_means_higher_level(self):
        self.assertEqual(snr_level(-20), 70)
        self.assertEqual(snr_level(-5), 55)
        self.assertEqual(snr_level(10), 40)
        self.assertEqual(snr_level(None), 50)
        self.assertEqual(snr_level(-100), 100)
        self.assertEqual(watts_level(50), 50)
        self.assertEqual(watts_level(1500), 100)

    def test_grid_space_covers_151_with_rare_legendaries(self):
        species = set()
        legends = 0
        for a in string.ascii_uppercase[:18]:
            for b in string.ascii_uppercase[:18]:
                for number in range(100):
                    name, _ = choose_species(f"{a}{b}{number:02d}")
                    species.add(name)
                    legends += name in LEGENDARY
        self.assertEqual(species, set(SPECIES))
        self.assertLess(legends, 650)
        self.assertGreater(legends, 0)
        self.assertEqual(grid4("cn79ab"), "CN79")
        self.assertEqual(grid4("SS73"), "")
        self.assertEqual(choose_species("CN79ab"), choose_species("CN79"))

    def test_habitat_stays_stable_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "dex.sqlite3")
            d = Dex(path)
            first = d.habitat("PM95", "JA1ABC")
            d.db.close()
            d = Dex(path)
            self.assertEqual(d.habitat("PM95", "JA2XYZ"), first)
            d.db.close()

    def test_rr73_captures_once_without_contact_log(self):
        self.begin()
        self.feed(wire.reception("N0CALL JA1ABC RR73", -20, 3))
        self.assertEqual(self.e.state, "success")
        self.assertEqual(len(self.dex.collection()), 1)
        self.assertEqual(self.dex.rows(), [])
        self.assertEqual(self.dex.collection()[0][3], "PM95")
        self.assertEqual(self.e.station_grids["JA1ABC"], "PM95")
        self.feed(wire.reception("N0CALL JA1ABC RR73", -20, 5))
        self.assertEqual(len(self.dex.collection()), 1)

    def test_rrr_needs_final_73(self):
        now = [0.0]
        self.e.clock = lambda: now[0]
        self.begin()
        self.feed(wire.reception("N0CALL JA1ABC RRR", -20, 3))
        self.assertEqual(len(self.dex.collection()), 0)
        self.feed(wire.status("JA1ABC N0CALL 73", True, target="JA1ABC"))
        self.assertEqual(len(self.dex.collection()), 0)
        now[0] = 13.2
        self.feed(wire.status("", False, target="JA1ABC"))
        self.e.poll()
        self.assertEqual(len(self.dex.collection()), 1)

    def test_aborted_final_transmission_does_not_capture(self):
        now = [0.0]
        self.e.clock = lambda: now[0]
        self.begin()
        self.feed(wire.reception("N0CALL JA1ABC R-07", -15, 3))
        self.feed(wire.status("JA1ABC N0CALL RR73", True, target="JA1ABC"))
        now[0] = 2
        self.feed(wire.status("", False, target="JA1ABC"))
        now[0] = 20
        self.e.poll()
        self.assertEqual(len(self.dex.collection()), 0)

    def test_late_grid_reveals_species(self):
        self.feed(wire.status("JA1ABC N0CALL CN79", True, target="JA1ABC"))
        self.assertEqual(self.e.grid, "")
        self.feed(wire.reception("N0CALL JA1ABC PM95", -20, 1))
        self.assertEqual(self.e.grid, "PM95")
        self.assertEqual(self.e.species, self.dex.habitat("PM95", "JA1ABC")[0])
        self.assertIn("identity", [a["type"] for a in self.e.actions])

    def test_plain_73_is_not_enough(self):
        self.begin()
        self.feed(wire.reception("N0CALL JA1ABC 73", -20, 3))
        self.assertEqual(len(self.dex.collection()), 0)

    def test_retries_do_not_advance_weakening(self):
        self.begin()
        self.feed(wire.reception("N0CALL JA1ABC R-07", -20, 3))
        first = self.e.actions[-1]["target_hp"]
        self.feed(wire.reception("N0CALL JA1ABC R-07", -25, 5))
        self.assertEqual(first, self.e.actions[-1]["target_hp"])
        self.assertEqual(self.e.progress, 3)


if __name__ == "__main__":
    unittest.main()

"""Integration test of actual emulator, timed binary packets, and Pokédex."""

from demo import real_sequence as sequence
from engine import Dex, Engine
from protocol import decode
from rom import ROOT, Red


def verify(missed_reply=False):
    now = [0.0]
    engine = Engine(Dex(":memory:"), clock=lambda: now[0])
    red = Red(clock=lambda: now[0])
    events = sequence(missed_reply=missed_reply)
    index = 0
    capture_frame = None
    miss_hp = None
    miss_result_time = None
    longest_menu = menu_frames = 0
    snapshots = {
        33: "callsign",
        3: "cq",
        38: "encounter",
        67: "attack",
        118: "await-log",
        139: "complete",
    }
    try:
        for frame in range(60 * 145):
            now[0] = frame / 60
            while index < len(events) and events[index][0] <= now[0]:
                engine.handle(decode(events[index][1]))
                index += 1
            engine.poll()
            while engine.actions:
                red.action(engine.actions.pop(0))
            red.tick(1)
            menu_frames = menu_frames + 1 if red.selecting_move else 0
            longest_menu = max(longest_menu, menu_frames)
            if red.active_missed:
                if miss_hp is None:
                    miss_hp = (red.read16("wBattleMonHP"), red.read16("wEnemyMonHP"))
                assert miss_hp == (red.read16("wBattleMonHP"), red.read16("wEnemyMonHP")), (
                    "Inferred missed attack changed HP"
                )
                if red.prompt == "result" and miss_result_time is None:
                    miss_result_time = now[0]
                if miss_result_time is not None and now[0] >= miss_result_time + 0.5:
                    red.image().resize((640, 576)).save(ROOT / "data/verified-miss.png")
                    miss_result_time = float("inf")
            if red.capture_seen and capture_frame is None:
                capture_frame = frame
            if capture_frame is not None and frame == capture_frame + 90:
                red.image().resize((640, 576)).save(ROOT / "data/verified-capture.png")
            assert not red.error, red.error
            if 30 <= now[0] < 38:
                assert red.damage_events == 0, "TX hit before charge time elapsed"
            assert len(red.pending) <= 3, "Animation queue is falling behind FT8"
            if frame % 60 == 0 and frame // 60 in snapshots:
                red.image().resize((640, 576)).save(
                    ROOT / "data" / f"verified-{snapshots[frame // 60]}.png"
                )
        assert engine.state == "success", engine.state
        assert engine.opponent == "JA1ABC"
        assert engine.attacks == (2 if missed_reply else 3), engine.attacks
        assert len(engine.dex.rows()) == 1
        assert red.mode == "victory", red.mode
        assert red.capture_seen
        assert red.read("wPartyCount") == 2
        assert len(engine.dex.collection()) == 1
        assert red.damage_events == 3, red.damage_events
        assert red.missed_events == int(missed_reply), red.missed_events
        assert longest_menu < 60, "Automatic selectors are still replacing native battle text"
        from pyboy.plugins.game_wrapper_pokemon_gen1_constants import (
            POKEMON_TEXT_ENCODING,
        )

        for symbol, expected in [
            ("wTrainerName", "JA1ABC"),
            ("wBattleMonNick", "N0CALL"),
            ("wEnemyMonNick", "JA1ABC"),
        ]:
            address = red.p.symbol_lookup(symbol)[1]
            encoded = [POKEMON_TEXT_ENCODING[c] for c in expected] + [0x50]
            assert list(red.p.memory[address : address + len(encoded)]) == encoded, symbol
        print(
            f"PASS: real 15-second slots; {engine.attacks} partner moves + 3 transmitted moves "
            f"+ {red.missed_events} native misses + capture; menus under 1s; exactly 1 logged QSO."
        )
    finally:
        red.close()
        engine.dex.db.close()


if __name__ == "__main__":
    verify()
    verify(missed_reply=True)

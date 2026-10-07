"""Verified English Red adapter. Runtime-only cinematic battle modifications.

The user's ROM and cartridge save are never overwritten. Bootstrap states are
private to this demo and bound to the ROM checksum and PyBoy version.
"""

import hashlib
import io
import time
from collections import deque
from pathlib import Path

from PIL import ImageDraw
from pyboy import PyBoy
from pyboy.plugins.game_wrapper_pokemon_gen1_constants import POKEMON_TEXT_ENCODING

from game_audio import GameAudio

ROOT = Path(__file__).resolve().parent
RED_SHA1 = "ea9bcae617fdf159b045185467ae58b2e4a48b9a"


class Red:
    def __init__(self, path=None, clock=time.monotonic):
        self.clock = clock
        self.audio = GameAudio()
        self.radio_phase = "LISTENING"
        self.radio_detail = "Receive window"
        self.slot_fraction = 0.0
        path = Path(path or ROOT / "Pokemon Red.gb")
        if hashlib.sha1(path.read_bytes()).hexdigest() != RED_SHA1:
            raise ValueError("ROM is not the supported English Pokémon Red revision")
        self.p = PyBoy(
            str(path),
            window="null",
            sound_emulated=True,
            sound_sample_rate=48000,
            ram_file=io.BytesIO(bytes(32768)),
            symbols=str(ROOT / "reference/pokered.sym"),
        )
        self.p.set_emulation_speed(0)
        self.mode = "idle"
        self.frame = 0
        self.entered_menu = False
        self.menu_settle = 0
        self.waiting = False
        self.pending = deque()
        self.finishing = False
        self.attack_damage = 12
        self.counter_damage = 12
        self.initialized_battle = False
        self.damage_events = 0
        self.completed_rounds = 0
        self.battle_started = 0
        self.move_started = 0
        self.error = ""
        self.active_side = "tx"
        self.selecting_move = False
        self.call = ""
        self.own = "N0CALL"
        self.state_path = ROOT / "data/grass-red-audio-2.8.1.state"
        self.state_path.parent.mkdir(exist_ok=True)
        if not self.state_path.exists():
            self.bootstrap()
        self.load_grass()
        self.theme_moves()
        self.p.hook_register(None, "GetTrainerName_.foundName", self._trainer_name, None)
        self.p.hook_register(None, "LoadEnemyMonData.statModLoop", self._names, None)
        self.p.hook_register(None, "PrintText", self._names, None)
        self.p.hook_register(None, "ExecutePlayerMove", self._player_turn, None)
        self.p.hook_register(None, "ExecuteEnemyMove", self._enemy_turn, None)
        self.p.hook_register(None, "DisplayBattleMenu", self._menu, None)
        self.p.hook_register(None, "ApplyDamageToEnemyPokemon", self._enemy_damage, None)
        self.p.hook_register(None, "ApplyDamageToPlayerPokemon", self._player_damage, None)

    def theme_moves(self):
        # Override only emulated ROM bytes; retain every entry's size and terminator.
        # Both move menus and attack narration read this same cartridge table.
        themes = {
            "SWIFT": "8-FSK",
            "TACKLE": "DECODE",
            "TAIL WHIP": "SNR DROP",
            "QUICK ATTACK": "DT DRIFT",
        }
        bank, address = self.p.symbol_lookup("MoveNames")
        reverse = {value: key for key, value in POKEMON_TEXT_ENCODING.items()}
        self.themed_moves = {}
        self.move_name_slot = None
        for _ in range(165):
            start = address
            raw = []
            while self.p.memory[bank, address] != 0x50:
                raw.append(self.p.memory[bank, address])
                address += 1
                if len(raw) > 20:
                    raise RuntimeError("Invalid move-name table")
            original = "".join(reverse.get(c, "?") for c in raw)
            if original == "SWIFT":
                self.move_name_slot = (bank, start, len(raw))
            if original in themes:
                themed = themes[original]
                assert len(themed) <= len(raw)
                encoded = [POKEMON_TEXT_ENCODING[c] for c in themed.ljust(len(raw))]
                self.p.memory[bank, start:address] = encoded
                self.themed_moves[original] = themed
            address += 1
        if len(self.themed_moves) != len(themes):
            raise RuntimeError("Could not locate all demonstration move names")

    def _player_turn(self, _):
        if self.active_side != "tx":
            self.write("wPlayerSelectedMove", 255)
        else:
            self.selecting_move = False

    def _enemy_turn(self, _):
        self.write("wEnemySelectedMove", 129 if self.active_side == "rx" else 255)
        if self.active_side == "rx":
            self.selecting_move = False

    def message_move(self, text):
        bank, address, length = self.move_name_slot
        encoded = [POKEMON_TEXT_ENCODING.get(c, 0x7F) for c in text[:length].ljust(length)]
        self.p.memory[bank, address : address + length] = encoded

    def name(self, symbol, text):
        # Gen I nickname buffers hold ten visible characters and a terminator.
        encoded = [POKEMON_TEXT_ENCODING.get(c, 0x7F) for c in text.upper()[:10]]
        encoded += [0x50] * (11 - len(encoded))
        addr = self.p.symbol_lookup(symbol)[1]
        self.p.memory[addr : addr + 11] = encoded

    def _trainer_name(self, _):
        if self.call:
            self.name("wNameBuffer", self.call)
            self.name("wTrainerName", self.call)

    def _names(self, _=None):
        self.name("wPlayerName", self.own)
        self.name("wPartyMonNicks", self.own)
        if self.mode == "battle":
            self.name("wTrainerName", self.call)
            self.name("wBattleMonNick", self.own)
            self.name("wEnemyMonNick", self.call)
            self.name("wEnemyMonNicks", self.call)

    def configure_names(self, event):
        self.own = event.get("own") or self.own
        self._names()

    def read16(self, name):
        addr = self.p.symbol_lookup(name)[1]
        return self.p.memory[addr] * 256 + self.p.memory[addr + 1]

    def write16(self, name, value):
        addr = self.p.symbol_lookup(name)[1]
        self.p.memory[addr] = value >> 8
        self.p.memory[addr + 1] = value & 255

    def write(self, name, value):
        self.p.memory[self.p.symbol_lookup(name)[1]] = value

    def read(self, name):
        return self.p.memory[self.p.symbol_lookup(name)[1]]

    def _menu(self, _):
        self.entered_menu = True
        self.selecting_move = True

    def _enemy_damage(self, _):
        hp = self.read16("wEnemyMonHP")
        self.write16("wDamage", hp if self.finishing else min(self.attack_damage, max(0, hp - 1)))
        self.damage_events += 1

    def _player_damage(self, _):
        # Visual counterattacks are retained without allowing a radio retry to black out.
        self.write16("wDamage", min(self.attack_damage, max(0, self.read16("wBattleMonHP") - 1)))

    def bootstrap(self):
        # Bounded Red-specific intro navigation; PyBoy's generic start_game assumes Blue names.
        for i in range(650):
            if i < 20:
                self.p.button("start")
            else:
                if self.p.tilemap_window[2, 4] in (145, 129) and self.p.tilemap_window[2, 2] == 141:
                    self.p.button("down")
                    self.p.tick(30)
                self.p.button("a")
            self.p.tick(30)
            if self.read("wCurMap") == 0x26 and i > 550:
                self.p.tick(180)
                break
        else:
            raise RuntimeError("Could not prepare Red intro within frame budget")
        self.p.game_wrapper.set_party([])
        self.p.game_wrapper.add_pokemon("PIKACHU", level=25, moves=["SWIFT"])
        self.p.game_wrapper.set_event_flag("got_starter")
        self.p.game_wrapper.set_event_flag("got_pokedex")
        self.p.game_wrapper.warp("route_1")
        self.p.tick(120)
        self.write("wRepelRemainingSteps", 255)
        self.p.button_press("right")
        self.p.tick(32)
        self.p.button_release("right")
        self.p.tick(8)
        if self.read("wCurMap") != 12 or self.read("wIsInBattle") != 0:
            raise RuntimeError("Grass scene validation failed")
        with self.state_path.open("wb") as f:
            self.p.save_state(f)

    def load_grass(self):
        self.audio.clear()
        self.selecting_move = False
        with self.state_path.open("rb") as f:
            self.p.load_state(f)
        for key in ("left", "right", "up", "down", "a", "b", "start", "select"):
            self.p.button_release(key)
        self.p.tick(1)
        # Injected demonstration party must obey regardless of its synthetic OT ID.
        self.p.game_wrapper.set_badge("earth")
        self.pending = deque()
        self.finishing = False
        self.attack_damage = 12
        self.counter_damage = 12
        self.waiting = False
        self.entered_menu = False
        self.initialized_battle = False
        self.menu_settle = 0
        self.error = ""

    def action(self, event):
        kind = event["type"]
        if kind in ("cq", "reset"):
            self.load_grass()
            self.mode = "cq" if kind == "cq" else "idle"
            self.configure_names(event)
        elif kind == "encounter":
            self.load_grass()
            self.call = event["call"]
            self.mode = "battle"
            self.configure_names(event)
            self.battle_started = self.frame
            self.move_started = self.frame
            self.damage_events = 0
            self.completed_rounds = 0
            self.p.game_wrapper.start_trainer_battle("YOUNGSTER", 1)
        elif kind == "attack":
            self.pending.append(event)
        elif kind == "success":
            self.pending.append(event)

    def tick(self, count=4):
        for _ in range(count):
            if self.error:
                return
            self.frame += 1
            if self.mode == "cq":
                self.write("wRepelRemainingSteps", 255)
                # Two-tile pacing loop fully inside the prepared grass patch.
                at = self.frame % 128
                if at == 0:
                    self.p.button_release("left")
                    self.p.button_press("right")
                if at == 32:
                    self.p.button_release("right")
                if at == 64:
                    self.p.button_press("left")
                if at == 96:
                    self.p.button_release("left")
            elif self.mode == "battle":
                if self.entered_menu:
                    self.entered_menu = False
                    self.menu_settle = 16
                    if not self.initialized_battle:
                        self.write("wEnemyPartyCount", 1)
                        self.write16("wBattleMonMaxHP", 100)
                        self.write16("wBattleMonHP", 100)
                        self.write16("wEnemyMonMaxHP", 100)
                        self.write16("wEnemyMonHP", 100)
                        self.initialized_battle = True
                    else:
                        self.completed_rounds += 1
                if self.menu_settle:
                    self.menu_settle -= 1
                    if self.menu_settle == 0:
                        self.waiting = True
                elif self.waiting:
                    if not self.pending:
                        self.advance_frame()  # Music keeps running at the hidden menu.
                        continue
                    if self.clock() < self.pending[0].get("not_before", 0):
                        self.advance_frame()
                        continue
                    event = self.pending.popleft()
                    self.finishing = event["type"] == "success"
                    self.active_side = event.get("side", "tx")
                    self.message_move(event.get("move", "LOG!"))
                    self.attack_damage = event.get("damage", 12)
                    self.counter_damage = event.get("counter_damage", 12)
                    self.waiting = False
                    self.move_started = self.frame
                    self.write("wCurrentMenuItem", 0)
                    self.write("wBattleMonStatus", 0)
                    self.write("wEnemyMonStatus", 0)
                    # Health persists across actual message turns.
                    self.p.button("a")
                elif self.frame % 24 == 0:
                    self.p.button("a")
                if self.initialized_battle and self.read("wIsInBattle") == 0:
                    self.mode = "victory"
                if not self.waiting and self.frame - self.move_started > 3600:
                    self.error = "ROM scene timed out. Restart demo to recover."
                    return
            self.advance_frame()

    def advance_frame(self):
        self.p.tick(1, True, self.audio.enabled)
        if self.audio.enabled:
            self.audio.push(self.p.sound.ndarray)

    def image(self):
        frame = self.p.screen.image.copy()
        if self.mode == "battle" and self.selecting_move:
            # Keep the emulator's automatic menu navigation out of the presentation.
            # Attack narration remains visible as soon as a message turn starts.
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 96, 159, 143), fill="white")
            draw.rectangle((2, 98, 157, 141), outline="black", width=1)
            draw.text((8, 102), self.radio_phase, fill="black")
            draw.text((8, 115), self.radio_detail, fill="black")
            draw.rectangle((8, 132, 151, 136), outline="black")
            fill = int(140 * self.slot_fraction)
            if fill:
                draw.rectangle((10, 133, 10 + fill, 135), fill="black")
        return frame

    def close(self):
        self.audio.close()
        self.p.stop(save=False)

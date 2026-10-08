# PokeFT8

A Windows desktop companion that turns WSJT-X FT8 contacts into wild Pokemon Red encounters, powered by PyBoy. Callsigns name the Pokemon, grid squares choose their species, and completed exchanges earn Poke Ball captures.

## Watch it in action

[![Watch the PokeFT8 demo on YouTube](https://img.youtube.com/vi/gJwGsVVMZYM/hqdefault.jpg)](https://www.youtube.com/watch?v=gJwGsVVMZYM)

[Watch the demo on YouTube](https://www.youtube.com/watch?v=gJwGsVVMZYM).

## Quick start

Requires Windows, Python 3.13 with Tkinter, and your own supported English Pokemon Red ROM. No ROM, save file, or Nintendo game assets are included or downloaded.

1. Clone this repository and open PowerShell in its folder.
2. Run `powershell -ExecutionPolicy Bypass -File .\Setup.ps1`.
3. Place your ROM at `Pokemon Red.gb` in that folder.
4. Double-click **Start-Demo.cmd** for a simulated contact, or **Start-Live.cmd** for WSJT-X.

Supported ROM SHA-1: `ea9bcae617fdf159b045185467ae58b2e4a48b9a`.
Other revisions are rejected before emulator hooks run. An alternate path can be supplied with `--rom`.

Setup installs pinned dependencies and downloads checksum-verified symbols from [pret/pokered](https://github.com/pret/pokered/tree/symbols). It does not fetch a ROM. The original cartridge file and save are never written; the app uses isolated RAM and a generated scene under `data/`.

## Connect WSJT-X

In WSJT-X's reporting settings, set the UDP server to `127.0.0.1` and port `2237`. The app listens locally and never sends commands or changes your radio settings. If another receiver occupies that port, choose another port in both applications:

```powershell
.venv\Scripts\python.exe -X utf8 app.py --live --port 2238
```

Only standard FT8 is supported, not contest or Fox/Hound modes. The first WSJT-X instance that sends a Status packet is selected. The companion has been tried with live telemetry; tests use synthetic binary packets and real-ROM replays.

## Encounters and capture

- Calling CQ walks through Route 1 grass. If several stations answer, the strongest directed reply starts the game encounter. This does not select your radio target.
- Calling a station directly starts its battle. Selecting a different DX call while TX is enabled or during battle changes partners. The actual transmitted address wins over a stale DX-call field.
- Your transmitted message is your move; each decoded partner message is theirs. The game shows payloads such as `-05`, `R-07`, and `RR73`, with full messages in the activity feed.
- Both start at 100 HP. As the exchange advances through grid, report, roger-report and final acknowledgements, the wild Pokemon's HP decreases to 80, 55, 25 and finally 5. Repeated messages do not advance this progress. The partner's moves still use received SNR for damage to you. This is game balance, not a measurement of radio power or distance.
- A completed receive/decode cycle with no partner reply shows a zero-damage inferred MISS. It cannot prove that a transmission was dropped, that the partner transmitted, or that they heard your message.
- Returning to CQ resets the battle. Three minutes without a partner reply returns to standby. Changing partners clears queued moves, reports and pending misses from the old encounter.
- After report exchange, received RR73, transmitted RR73 following their report, or RRR followed by 73 triggers a real, guaranteed Poke Ball capture. Transmitted final acknowledgements wait for the transmit interval before the animation. Captures are recorded separately from official WSJT-X log events; later logged-QSO packets confirm the contact without creating another capture. A logged QSO is also a fallback when acknowledgement packets were missed. This collection does not write to or replace WSJT-X's log.

## Levels and grid habitats

Weaker signals mean stronger wild Pokemon: level = `clamp(50 - received SNR, 1, 100)`. For example, -20 dB means level 70, -5 means 55, and +10 means 40. With no decode yet, level 50 is provisional. Your level uses manually configured watts, default **50 W**, clamped to Red's level range 1..100. The power field accepts 0.1..1500 W and persists locally; WSJT-X does not supply live transmitter watts.

Four-character Maidenhead squares map deterministically across all 151 original species. Subsquare suffixes share their parent habitat. Species assignments are saved on first discovery. Grids new to your local contact log have a 1% legendary pool and 14% rare pool; already-worked grids get 0.1% and 1.9% respectively. The remaining assignments use common species. These are game rarity weights based on local novelty, not measured worldwide grid rarity or population. No location lookup or external tracking service is used.

When the grid is unknown, a deterministic callsign-based common species appears provisionally. A subsequently decoded grid reveals its mapped species. Callsigns remain the in-game nicknames, while species and grid appear in the companion's collection.

## Controls and pacing

**Restart demo** runs a roughly two-minute simulated exchange using real 15-second FT8 slots. **Pause** freezes the demo. **Listen to WSJT-X** switches to live telemetry. **Sound: Off / On** toggles Game Boy audio, muted on startup. **Save frame** writes a screenshot under `data/`.

Outgoing moves build up for ten seconds and decoded replies for two seconds before their animation is eligible to play. The hidden selection panel shows the Pokemon readying its message move or sizing up its opponent, filling the slot instead of displaying a generic wait. Radio phase and slot progress remain in the companion UI. Audio uses the Game Boy clock independently of screen redraws and continues through radio waits. Original Pokemon graphics and move animations are retained. In-game names are limited to ten characters; full callsigns remain in the dashboard and log.

Demo contacts are in memory. Live contacts are saved in `data/contacts.sqlite3`. All data, captures, ROMs and generated save states are ignored by Git. To rebuild the starting scene, close the app and remove only `data/grass-red-audio-2.8.1.state`.

## Development and checks

```powershell
.venv\Scripts\python.exe -m unittest discover -v
.venv\Scripts\python.exe -X utf8 verify_session.py
```

The unit tests require only Python and run in GitHub Actions without a ROM. The integration replay requires the local ROM and symbols; it checks battle completion, callsign naming, timing and queue bounds and writes screenshots under `data/`.

`engine.py` owns the QSO state machine; `protocol.py` handles WSJT-X binary packets; `rom.py` controls the emulator; `game_audio.py` queues audio; `app.py` provides the desktop UI. `demo.py` includes realistic and compressed test fixtures.

## References

- [WSJT-X UDP protocol](https://github.com/WSJTX/wsjtx/blob/master/Network/NetworkMessage.hpp)
- [WSJT-X user guide](https://wsjt.sourceforge.io/wsjtx-main_en.html)
- [PyBoy](https://github.com/Baekalfen/PyBoy)
- [Pokemon Red disassembly and symbols](https://github.com/pret/pokered)

Unofficial hobby project; not affiliated with Nintendo, The Pokemon Company, or the WSJT-X developers. Third-party projects retain their respective licenses. No license grant for the original game is implied.

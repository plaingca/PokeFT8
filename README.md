# PokeFT8

A desktop companion for Windows, Linux and macOS that turns WSJT-X FT8 contacts into wild Pokemon Red encounters, powered by PyBoy. Callsigns name the Pokemon, grid squares choose their species, and completed exchanges earn Poke Ball captures.

## Watch it in action

[![Watch the PokeFT8 demo on YouTube](https://img.youtube.com/vi/gJwGsVVMZYM/hqdefault.jpg)](https://www.youtube.com/watch?v=gJwGsVVMZYM)

[Watch the demo on YouTube](https://www.youtube.com/watch?v=gJwGsVVMZYM).

## Quick start

### Portable downloads (no Python installation)

Open the latest successful [Portable packages workflow run](https://github.com/plaingca/PokeFT8/actions/workflows/portable.yml) and download the artifact for your computer: **windows-x64**, **linux-x64**, **macos-arm64** (Apple Silicon), or **macos-x64** (Intel). GitHub requires signing in to download Actions artifacts. Each contains an archive and its SHA-256 checksum. Artifacts are retained for 30 days; version tags also attach all four archives to a draft GitHub release.

1. Extract the entire archive into a writable folder. Keep all included support files together.
2. Launch `PokeFT8.exe` on Windows, `./PokeFT8` on Linux, or `PokeFT8.app` on macOS.
3. Place your own supported `Pokemon Red.gb` beside the executable (beside the `.app` on macOS), or select it in the file picker on startup.

The default launch runs the demo. Pass `--live` to listen to WSJT-X immediately, or use **Listen to WSJT-X** in the app. Settings, contacts and generated emulator states remain in a local `data/` folder beside the executable/app. The supplied Python, Tk, emulator, SDL2 and symbols do not need a separate installation. No ROM, saves, contacts or video recordings are distributed.

Packages target Windows x64, desktop Linux x64 with glibc 2.35 or newer (Ubuntu 22.04 or newer), and macOS 15 or newer on the matching architecture. Linux needs a graphical desktop with X11/XWayland and standard desktop/audio libraries. Builds are unsigned: Windows may display SmartScreen, and macOS may require approving the app in **System Settings > Privacy & Security**. Keep the portable folder in a user-writable location.

### Run from source on Windows

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

Automatic button presses pace the native battle narration across the radio slots. Move text starts as soon as its turn can be selected; the attack animation waits until ten seconds into an outgoing transmission or two seconds after a decoded reply. The ROM keeps the completed move's text visible until the next turn, instead of showing a waiting or sizing-up screen. Missing an expected reply after a complete decode cycle produces Red's actual zero-damage "attack missed" result; the feed identifies it as inferred. The demo includes one such miss followed by a retry. Radio phase and slot progress remain in the companion UI. Audio uses the Game Boy clock independently of screen redraws and continues through the native button prompts. Original Pokemon graphics and move animations are retained. In-game names are limited to ten characters; full callsigns remain in the dashboard and log.

Demo contacts are in memory. Live contacts are saved in `data/contacts.sqlite3`. All data, captures, ROMs and generated save states are ignored by Git. To rebuild the starting scene, close the app and remove only `data/grass-red-audio-2.8.1.state`.

## Development and checks

```powershell
.venv\Scripts\python.exe -m unittest discover -v
.venv\Scripts\python.exe -X utf8 verify_session.py
```

The unit tests require only Python and run in GitHub Actions without a ROM. The integration replay requires the local ROM and symbols; it checks battle completion, callsign naming, timing and queue bounds and writes screenshots under `data/`.

To build a portable package on its target OS, install `requirements-build.txt`, run `python prepare_reference.py`, then run `python packaging/build_package.py --label windows-x64` (or the matching Linux/macOS label). On a headless Linux builder, run the build under `xvfb-run -a`. The builder verifies pinned symbols, checks for excluded game/private files, launches the frozen executable from another directory to test Tk/SDL/emulator imports, and writes the archive plus checksum under `artifacts/`. The Actions workflow runs these checks on all four native runner architectures for every main push, pull request or manual dispatch. Pushing a `v*` tag creates or updates a draft release; it does not publish that release automatically.

`engine.py` owns the QSO state machine; `protocol.py` handles WSJT-X binary packets; `rom.py` controls the emulator; `game_audio.py` queues audio; `app.py` provides the desktop UI. `demo.py` includes realistic and compressed test fixtures.

## References

- [WSJT-X UDP protocol](https://github.com/WSJTX/wsjtx/blob/master/Network/NetworkMessage.hpp)
- [WSJT-X user guide](https://wsjt.sourceforge.io/wsjtx-main_en.html)
- [PyBoy](https://github.com/Baekalfen/PyBoy)
- [Pokemon Red disassembly and symbols](https://github.com/pret/pokered)

Unofficial hobby project; not affiliated with Nintendo, The Pokemon Company, or the WSJT-X developers. Third-party projects retain their respective licenses. No license grant for the original game is implied.

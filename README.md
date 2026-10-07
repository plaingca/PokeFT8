# PokeFT8

A Windows desktop companion that turns WSJT-X FT8 contacts into real Pokemon Red battles, powered by PyBoy. Callsigns name the trainers and Pokemon; transmitted and decoded messages become their moves.

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

## Battle behavior

- Calling CQ walks through Route 1 grass. If several stations answer, the strongest directed reply starts the game encounter. This does not select your radio target.
- Calling a station directly starts its battle. Selecting a different DX call while TX is enabled or during battle changes partners. The actual transmitted address wins over a stale DX-call field.
- Your transmitted message is your move; each decoded partner message is theirs. The game shows payloads such as `-05`, `R-07`, and `RR73`, with full messages in the activity feed.
- Both start at 100 HP. Your attack strength uses their last report of you; their strength uses your current decode SNR. Damage is `6 + clamp(SNR + 24, 0, 24)`, with provisional 12 HP when your report is unknown. This is game balance, not a measurement of radio power or distance.
- A completed receive/decode cycle with no partner reply shows a zero-damage inferred MISS. It cannot prove that a transmission was dropped, that the partner transmitted, or that they heard your message.
- Returning to CQ resets the battle. Three minutes without a partner reply returns to standby. Changing partners clears queued moves, reports and pending misses from the old encounter.
- Only a matching logged QSO awards victory and adds a callsign to the companion's Pokedex. Health cannot fall below 1 before that finishing move. This collection does not replace WSJT-X's log.

## Controls and pacing

**Restart demo** runs a roughly two-minute simulated exchange using real 15-second FT8 slots. **Pause** freezes the demo. **Listen to WSJT-X** switches to live telemetry. **Sound: Off / On** toggles Game Boy audio, muted on startup. **Save frame** writes a screenshot under `data/`.

Outgoing moves charge for eight seconds before their animation is eligible to play. Listening, transmitting and decoding indicators fill the hidden battle menu. Audio uses the Game Boy clock independently of screen redraws and continues through radio waits. Original Pokemon graphics and move animations are retained. In-game names are limited to ten characters; full callsigns remain in the dashboard and log.

Demo contacts are in memory. Live contacts are saved in `data/contacts.sqlite3`. All data, captures, ROMs and generated save states are ignored by Git. To rebuild the starting scene, close the app and remove only `data/grass-red-audio-2.8.1.state`.

## Development and checks

```powershell
.venv\Scripts\python.exe -m unittest -v test_demo
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

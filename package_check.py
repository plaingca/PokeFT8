"""Exercise bundled native dependencies and Tk without a game ROM or radio."""

import hashlib
import json
import platform
import sys
import tkinter as tk

import sdl2
from PIL import Image
from pyboy import PyBoy

from prepare_reference import SHA256
from runtime_paths import BUNDLE_ROOT, ROOT


def startup_check(output):
    symbols = BUNDLE_ROOT / "reference/pokered.sym"
    if hashlib.sha256(symbols.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Bundled symbols failed checksum verification")
    version = sdl2.SDL_version()
    sdl2.SDL_GetVersion(version)
    if version.major != 2 or not PyBoy:
        raise RuntimeError("Native emulator or SDL2 failed to load")
    image = Image.new("RGB", (160, 144))
    assert image.size == (160, 144)
    root = tk.Tk()
    try:
        root.withdraw()
        root.update()
        tk_version = root.tk.call("info", "patchlevel")
    finally:
        root.destroy()
    output.write_text(
        json.dumps(
            {
                "ok": True,
                "frozen": bool(getattr(sys, "frozen", False)),
                "platform": sys.platform,
                "architecture": platform.machine(),
                "tk": tk_version,
                "sdl": f"{version.major}.{version.minor}.{version.patch}",
                "resource_root": str(BUNDLE_ROOT),
                "portable_root": str(ROOT),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

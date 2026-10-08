"""Keep portable user files separate from bundled, read-only resources."""

import sys
from pathlib import Path


def portable_root(executable, platform):
    executable = Path(executable).resolve()
    if platform == "darwin" and executable.parent.name == "MacOS":
        return executable.parents[3]  # Folder containing PokeFT8.app.
    return executable.parent


BUNDLE_ROOT = Path(__file__).resolve().parent
ROOT = portable_root(sys.executable, sys.platform) if getattr(sys, "frozen", False) else BUNDLE_ROOT

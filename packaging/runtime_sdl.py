"""Load the SDL libraries shipped with this package, rather than host copies."""

import os
import sys
from pathlib import Path

os.environ["PYSDL2_DLL_PATH"] = str(Path(sys._MEIPASS) / "sdl2dll" / "dll")

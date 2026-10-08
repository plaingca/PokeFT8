# Build a native one-folder package; never include the workspace or user data.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent
datas = [(str(project / "reference" / "pokered.sym"), "reference")]
binaries = []
hiddenimports = []
for package in ("pyboy", "sdl2dll"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports

a = Analysis(
    [str(project / "app.py")],
    pathex=[str(project)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    runtime_hooks=[str(project / "packaging" / "runtime_sdl.py")],
    excludes=["pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PokeFT8",
    console=sys.platform not in ("win32", "darwin"),
    upx=False,
)
bundle = COLLECT(exe, a.binaries, a.datas, name="PokeFT8", upx=False)
if sys.platform == "darwin":
    app = BUNDLE(
        bundle,
        name="PokeFT8.app",
        bundle_identifier="ca.ft8.pokeft8",
        info_plist={"NSHighResolutionCapable": True},
    )

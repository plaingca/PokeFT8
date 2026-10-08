"""Build, smoke-test, and archive one portable package on its native OS."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def check_contents(folder):
    forbidden = {".gb", ".gbc", ".sav", ".ram", ".state", ".sqlite", ".sqlite3", ".log"}
    for path in folder.rglob("*"):
        if path.is_file() and (path.suffix.lower() in forbidden or path.name.startswith(".env")):
            raise RuntimeError(
                f"Private or game content found in package: {path.relative_to(folder)}"
            )


def dependency_notices(folder):
    licenses = folder / "third-party-licenses"
    licenses.mkdir()
    lines = ["Bundled third-party dependencies and their installed license notices:"]
    for name in ("pyboy", "numpy", "pillow", "PySDL2", "pysdl2-dll", "pyinstaller"):
        dist = metadata.distribution(name)
        lines.append(f"\n{name} {dist.version}")
        for file in dist.files or []:
            if any(word in file.name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file() and source.suffix.lower() not in (".py", ".pyc", ".pyd"):
                    target = licenses / name / str(file)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    lines.append(f"  {target.relative_to(folder).as_posix()}")
    lines += [
        "\nPyBoy source: https://github.com/Baekalfen/PyBoy/tree/v2.8.1",
        "Pinned symbol source: see prepare_reference.py in the PokeFT8 repository.",
        "No Pokemon ROM, cartridge save, or original game assets are included.",
    ]
    (folder / "THIRD-PARTY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--label", required=True, choices=["windows-x64", "linux-x64", "macos-arm64", "macos-x64"]
    )
    args = parser.parse_args()
    from prepare_reference import SHA256

    symbols = PROJECT / "reference/pokered.sym"
    if hashlib.sha256(symbols.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Run prepare_reference.py to install the verified symbols")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "packaging/PokeFT8.spec"],
        cwd=PROJECT,
        check=True,
    )
    bundle = PROJECT / "dist" / ("PokeFT8.app" if sys.platform == "darwin" else "PokeFT8")
    check_contents(bundle)
    executable = bundle / (
        "Contents/MacOS/PokeFT8"
        if sys.platform == "darwin"
        else "PokeFT8.exe"
        if sys.platform == "win32"
        else "PokeFT8"
    )
    report = PROJECT / "build" / f"self-test-{args.label}.json"
    report.unlink(missing_ok=True)
    # Invoke from a different directory to catch accidental CWD dependencies.
    subprocess.run(
        [str(executable), "--self-test", str(report)],
        cwd=PROJECT / "build",
        check=True,
        timeout=120,
    )
    result = json.loads(report.read_text(encoding="utf-8"))
    expected_arch = "arm64" if args.label.endswith("arm64") else "x64"
    actual_arch = result["architecture"].lower()
    if (
        not result["ok"]
        or not result["frozen"]
        or (expected_arch == "arm64" and actual_arch not in ("arm64", "aarch64"))
        or (expected_arch == "x64" and actual_arch not in ("amd64", "x86_64"))
    ):
        raise RuntimeError(f"Frozen startup or architecture check failed: {result}")
    if Path(result["portable_root"]) != bundle.parent.resolve() and sys.platform == "darwin":
        raise RuntimeError("Portable data path is inside the macOS application bundle")
    artifacts = PROJECT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="portable-", dir=PROJECT / "build") as temp:
        stage = Path(temp) / "PokeFT8"
        if sys.platform == "darwin":
            stage.mkdir()
            shutil.copytree(bundle, stage / bundle.name, symlinks=True)
        else:
            shutil.copytree(bundle, stage, symlinks=True)
        shutil.copy2(PROJECT / "README.md", stage / "README.md")
        dependency_notices(stage)
        (stage / "START-HERE.txt").write_text(
            "PokeFT8 portable package\n\n"
            "Extract the whole archive into a writable folder. No Python installation is needed.\n"
            "Run PokeFT8.exe (Windows), ./PokeFT8 (Linux), or PokeFT8.app (macOS).\n"
            "Place your supported English Pokemon Red.gb next to the executable/app,\n"
            "or choose your own ROM in the file picker. No ROM is supplied.\n"
            "Settings and contacts are stored in data/ beside the executable/app.\n"
            "Use --live to start the receive-only WSJT-X listener; default is the demo.\n"
            "See README.md for platform requirements and unsigned-app instructions.\n",
            encoding="utf-8",
        )
        check_contents(stage)
        stem = artifacts / f"PokeFT8-{args.label}"
        if sys.platform == "win32":
            archive = Path(shutil.make_archive(str(stem), "zip", temp, "PokeFT8"))
        else:
            archive = stem.with_suffix(".tar.gz")
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(stage, arcname="PokeFT8")  # Preserve executable bits and .app symlinks.
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (artifacts / (archive.name + ".sha256")).write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    print(f"Verified portable package: {archive.name} ({archive.stat().st_size:,} bytes)")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT))
    main()

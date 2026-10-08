"""Portable paths and private-file exclusion, without native dependencies."""

# Load the build helper without shadowing the third-party 'packaging' library.
import importlib.util
import tempfile
import unittest
from pathlib import Path

from runtime_paths import portable_root

spec = importlib.util.spec_from_file_location(
    "build_package", Path(__file__).parent / "packaging/build_package.py"
)
build_package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_package)


class PackagingTests(unittest.TestCase):
    def test_data_stays_beside_executable_even_from_different_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp).resolve()
            self.assertEqual(portable_root(folder / "PokeFT8.exe", "win32"), folder)
            self.assertEqual(portable_root(folder / "PokeFT8", "linux"), folder)
            self.assertEqual(
                portable_root(folder / "PokeFT8.app/Contents/MacOS/PokeFT8", "darwin"), folder
            )

    def test_package_rejects_game_and_private_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ("Pokemon Red.gb", "contacts.sqlite3", "grass.state", ".env", "game.sav"):
                with self.subTest(name=name):
                    private = folder / name
                    private.write_bytes(b"private")
                    with self.assertRaises(RuntimeError):
                        build_package.check_contents(folder)
                    private.unlink()
            (folder / "pokered.sym").write_bytes(b"symbols")
            build_package.check_contents(folder)


if __name__ == "__main__":
    unittest.main()

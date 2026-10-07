"""Fetch checksum-pinned emulator symbols; no ROM or game assets are fetched."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

URL = (
    "https://raw.githubusercontent.com/pret/pokered/"
    "9a0c03834a435e38564445053ae9f9ece9999909/pokered.sym"
)
SHA256 = "cb30d0cc5e05875ceda3e2f2abcf55245afe2dc0fe2bf841b042b473c4a7dfb3"


def main():
    with urlopen(URL, timeout=30) as response:
        data = response.read(2_000_000)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("Symbol checksum mismatch; nothing was installed")
    path = Path(__file__).resolve().parent / "reference" / "pokered.sym"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(data)
    print("Verified emulator symbols installed.")


if __name__ == "__main__":
    main()

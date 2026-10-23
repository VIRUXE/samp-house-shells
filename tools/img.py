"""Minimal GTA SA IMG v2 archive reader/writer.

usage: python tools/img.py extract <archive.img> <out dir> <name> [name ...]
       python tools/img.py build <archive.img> <file> [file ...]
"""

import struct
import sys
from pathlib import Path

SECTOR = 2048


def read_dir(data: bytes) -> dict[str, tuple[int, int]]:
    """Lower-case entry name -> (byte offset, byte size)."""
    assert data[:4] == b"VER2", "not an IMG v2 archive"
    entries = {}
    for i in range(struct.unpack_from("<I", data, 4)[0]):
        offset, streaming, size, name = struct.unpack_from("<IHH24s", data, 8 + i * 32)
        entries[name.split(b"\0")[0].decode("latin-1").lower()] = (offset * SECTOR, (streaming or size) * SECTOR)
    return entries


def extract(archive: Path, out: Path, names: list[str]) -> None:
    data = archive.read_bytes()
    entries = read_dir(data)
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        offset, size = entries[name.lower()]
        (out / name).write_bytes(data[offset : offset + size])


def build(archive: Path, files: list[Path]) -> None:
    """Write files into a new archive; each is padded to whole sectors after the directory."""
    header = 8 + 32 * len(files)
    sector = (header + SECTOR - 1) // SECTOR
    directory, blobs = bytearray(b"VER2" + struct.pack("<I", len(files))), bytearray()
    for f in files:
        blob = f.read_bytes()
        sectors = (len(blob) + SECTOR - 1) // SECTOR
        assert len(f.name) < 24, f"{f.name}: IMG names are at most 23 characters"
        directory += struct.pack("<IHH24s", sector, sectors, 0, f.name.encode("latin-1"))
        blobs += blob + b"\0" * (sectors * SECTOR - len(blob))
        sector += sectors
    archive.write_bytes(bytes(directory) + b"\0" * ((header + SECTOR - 1) // SECTOR * SECTOR - len(directory)) + bytes(blobs))


if __name__ == "__main__":
    command, archive, *rest = sys.argv[1:]
    if command == "extract":
        extract(Path(archive), Path(rest[0]), rest[1:])
    elif command == "build":
        build(Path(archive), [Path(p) for p in rest])
    else:
        sys.exit(__doc__)

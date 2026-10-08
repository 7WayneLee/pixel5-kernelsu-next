"""Shared validation for the pinned Pixel 5 build and local boot packer."""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "redfin-up1a-231105-001-b2"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def profile(name: str = PROFILE_ID) -> dict:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError("Invalid profile name")
    p = json.loads((ROOT / "profiles" / f"{name}.json").read_text())
    if p["id"] != name or p["device"] != "redfin":
        raise ValueError("This project currently supports Pixel 5 / redfin only")
    for key in ("kernel_revision", "next_revision"):
        if not re.fullmatch(r"[0-9a-f]{40}", p[key]):
            raise ValueError(f"{key} must be an immutable commit")
    return p


def symvers(path: Path) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 3 or not re.fullmatch(r"0x[0-9a-fA-F]{8}", fields[0]):
            raise ValueError(f"Malformed Module.symvers line: {line!r}")
        crc = fields[0].lower()
        if fields[1] in symbols and symbols[fields[1]] != crc:
            raise ValueError(f"Conflicting CRC for {fields[1]}")
        symbols[fields[1]] = crc
    if not symbols:
        raise ValueError("Module.symvers is empty")
    return symbols


def compare_abi(before: dict[str, str], after: dict[str, str]) -> dict:
    removed = sorted(set(before) - set(after))
    changed = {name: {"stock": crc, "next": after[name]}
               for name, crc in before.items() if name in after and after[name] != crc}
    return {"compatible": not removed and not changed,
            "baseline_symbols": len(before), "next_symbols": len(after),
            "removed": removed, "changed": changed}


def config_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    return values


def module_versions(data: bytes) -> tuple[dict[str, str], str]:
    """Read arm64 ELF module import CRCs and vermagic without executing it."""
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected a little-endian ELF64 kernel module")
    if struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Module is not arm64")
    shoff = struct.unpack_from("<Q", data, 40)[0]
    size, count, string_index = struct.unpack_from("<HHH", data, 58)
    if size != 64 or not count or string_index >= count or shoff + size * count > len(data):
        raise ValueError("Invalid ELF section table")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * size)
                for i in range(count)]

    def contents(section):
        start, length = section[4:6]
        if start + length > len(data):
            raise ValueError("Truncated ELF section")
        return data[start:start + length]

    names = contents(sections[string_index])
    versions, release = {}, ""
    for section in sections:
        if section[0] >= len(names):
            raise ValueError("Invalid ELF section name")
        name = names[section[0]:].split(b"\0", 1)[0]
        if name not in (b"__versions", b".modinfo"):
            continue
        content = contents(section)
        if name == b"__versions":
            if len(content) % 64:
                raise ValueError("Invalid modversion record size")
            for offset in range(0, len(content), 64):
                crc = struct.unpack_from("<Q", content, offset)[0]
                symbol = content[offset + 8:offset + 64].split(b"\0", 1)[0].decode("ascii")
                versions[symbol] = f"0x{crc:08x}"
        else:
            for item in content.split(b"\0"):
                if item.startswith(b"vermagic="):
                    release = item.decode().split("=", 1)[1].split()[0]
    if not versions or not release:
        raise ValueError("Module lacks version CRCs or vermagic")
    return versions, release


def cpio_entries(data: bytes):
    """Read newc CPIO in memory; never extract paths from an archive."""
    offset = 0
    seen = set()
    while offset + 110 <= len(data):
        if data[offset:offset + 6] != b"070701":
            raise ValueError("Expected newc CPIO")
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        length, namesize = fields[6], fields[11]
        if namesize < 1 or offset + 110 + namesize > len(data):
            raise ValueError("Invalid CPIO name")
        raw_name = data[offset + 110:offset + 110 + namesize]
        if raw_name[-1:] != b"\0":
            raise ValueError("Unterminated CPIO name")
        name = raw_name[:-1].decode()
        start = (offset + 110 + namesize + 3) & ~3
        if start + length > len(data):
            raise ValueError("Truncated CPIO data")
        if name == "TRAILER!!!":
            return
        if name in seen:
            raise ValueError(f"Duplicate CPIO entry: {name}")
        seen.add(name)
        yield name, data[start:start + length]
        offset = (start + length + 3) & ~3
    raise ValueError("Missing CPIO trailer")


def boot_parts(data: bytes) -> tuple[bytes, bytes]:
    if len(data) < 4096 or data[:8] != b"ANDROID!":
        raise ValueError("Not an Android boot image")
    if struct.unpack_from("<I", data, 40)[0] != 3:
        raise ValueError("Only Pixel 5 boot header v3 is supported")
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from("<4I", data, 8)
    ramdisk_offset = 4096 + ((kernel_size + 4095) & ~4095)
    if not kernel_size or header_size != 1580 or ramdisk_offset + ramdisk_size > len(data):
        raise ValueError("Invalid boot image sizes")
    return data[4096:4096 + kernel_size], data[ramdisk_offset:ramdisk_offset + ramdisk_size]


def replace_kernel(stock: bytes, kernel: bytes) -> bytes:
    _, ramdisk = boot_parts(stock)
    if not kernel or kernel[:4] not in (b"\x04\x22\x4d\x18", b"\x02\x21\x4c\x18"):
        raise ValueError("Expected Image.lz4; do not use Image.lz4-dtb")
    header = bytearray(stock[:4096])
    struct.pack_into("<I", header, 8, len(kernel))
    payload = bytes(header) + kernel
    payload += bytes((-len(payload)) % 4096)
    payload += ramdisk
    payload += bytes((-len(payload)) % 4096)
    if len(payload) > len(stock) - 4096:
        raise ValueError("Patched image exceeds the partition capacity")
    # The original AVB hash/signature is invalid after changing the kernel.
    # Remove its metadata; this image is for an already-unlocked bootloader.
    return payload + bytes(len(stock) - len(payload))

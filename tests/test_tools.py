"""Checks for image corruption, profile mistakes and incompatible module CRCs."""
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from common import (ROOT, boot_parts, compare_abi, config_values, cpio_entries,
                    digest, module_versions, profile, replace_kernel, symvers)
from pack_boot import check_artifact, pack


def boot_image(kernel=b"old", ramdisk=b"original-ramdisk"):
    data = bytearray(32768)
    data[:8] = b"ANDROID!"
    struct.pack_into("<4I", data, 8, len(kernel), len(ramdisk), 0x1C00017B, 1580)
    struct.pack_into("<I", data, 40, 3)
    data[4096:4096 + len(kernel)] = kernel
    offset = 4096 + ((len(kernel) + 4095) & ~4095)
    data[offset:offset + len(ramdisk)] = ramdisk
    data[-64:-60] = b"AVBf"
    return bytes(data)


def elf_module(crc=0x12345678, release="4.19.278-test"):
    names = b"\0.shstrtab\0__versions\0.modinfo\0"
    imports = struct.pack("<Q", crc) + b"module_layout\0".ljust(56, b"\0")
    info = f"vermagic={release} SMP preempt mod_unload modversions aarch64\0".encode()
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 183)
    offsets = []
    for item in (names, imports, info):
        offsets.append(len(data))
        data += item
    data += bytes((-len(data)) % 8)
    section_start = len(data)
    struct.pack_into("<Q", data, 40, section_start)
    struct.pack_into("<HHH", data, 58, 64, 4, 1)
    data += bytes(64)
    for name, offset, content in zip((1, 11, 22), offsets, (names, imports, info)):
        data += struct.pack("<IIQQQQIIQQ", name, 1, 0, 0, offset, len(content), 0, 0, 1, 0)
    return bytes(data)


def cpio(items):
    data = bytearray()
    for name, content in list(items) + [("TRAILER!!!", b"")]:
        fields = [1, 0o100644, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name) + 1, 0]
        data += b"070701" + "".join(f"{value:08x}" for value in fields).encode()
        data += name.encode() + b"\0"
        data += bytes((-len(data)) % 4)
        data += content
        data += bytes((-len(data)) % 4)
    return bytes(data)


class BootTests(unittest.TestCase):
    def test_replacement_moves_ramdisk_and_preserves_header(self):
        stock = boot_image()
        kernel = b"\x04\x22\x4d\x18" + b"new" * 3000
        actual = replace_kernel(stock, kernel)
        self.assertEqual(boot_parts(actual), (kernel, b"original-ramdisk"))
        self.assertEqual(len(actual), len(stock))
        self.assertEqual(actual[:8], stock[:8])
        self.assertEqual(actual[12:4096], stock[12:4096])
        self.assertNotEqual(actual[-64:-60], b"AVBf")

    def test_rejects_wrong_header(self):
        stock = bytearray(boot_image())
        struct.pack_into("<I", stock, 40, 4)
        with self.assertRaisesRegex(ValueError, "header v3"):
            replace_kernel(bytes(stock), b"\x04\x22\x4d\x18test")

    def test_rejects_truncated_ramdisk(self):
        stock = bytearray(boot_image())
        struct.pack_into("<I", stock, 12, len(stock) * 2)
        with self.assertRaises(ValueError):
            boot_parts(stock)

    def test_rejects_oversized_kernel(self):
        with self.assertRaisesRegex(ValueError, "capacity"):
            replace_kernel(boot_image(), b"\x04\x22\x4d\x18" + bytes(40000))

    def test_rejects_uncompressed_image(self):
        with self.assertRaisesRegex(ValueError, "Image.lz4"):
            replace_kernel(boot_image(), b"ARMdtest")


class ModuleTests(unittest.TestCase):
    def test_reads_arm64_module_imports(self):
        imports, release = module_versions(elf_module())
        self.assertEqual(imports, {"module_layout": "0x12345678"})
        self.assertEqual(release, "4.19.278-test")

    def test_rejects_wrong_architecture(self):
        data = bytearray(elf_module())
        struct.pack_into("<H", data, 18, 62)
        with self.assertRaisesRegex(ValueError, "arm64"):
            module_versions(data)

    def test_rejects_elf_section_out_of_bounds(self):
        data = bytearray(elf_module())
        struct.pack_into("<Q", data, 40, len(data) + 100)
        with self.assertRaises(ValueError):
            module_versions(data)

    def test_added_symbols_are_compatible(self):
        self.assertTrue(compare_abi({"x": "0x1"}, {"x": "0x1", "ksu": "0x2"})["compatible"])

    def test_changed_or_removed_symbols_are_rejected(self):
        self.assertFalse(compare_abi({"x": "0x1"}, {"x": "0x2"})["compatible"])
        self.assertFalse(compare_abi({"x": "0x1"}, {})["compatible"])

    def test_cpio_is_read_without_extracting(self):
        self.assertEqual(list(cpio_entries(cpio([("lib/modules/x.ko", b"payload")]))),
                         [("lib/modules/x.ko", b"payload")])

    def test_truncated_cpio_is_rejected(self):
        data = cpio([("lib/modules/x.ko", b"payload")])
        with self.assertRaises(ValueError):
            list(cpio_entries(data[:130]))

    def test_duplicate_cpio_module_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            list(cpio_entries(cpio([("x.ko", b"one"), ("x.ko", b"two")])))


class ProfileTests(unittest.TestCase):
    def test_profile_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            profile("../../unrelated")

    def test_all_source_commits_are_pinned(self):
        p = profile()
        lock = json.loads((ROOT / p["source_lock"]).read_text())
        kernel = [item for item in lock["projects"] if item["path"] == "private/msm-google"]
        self.assertEqual(kernel[0]["revision"], p["kernel_revision"])
        self.assertEqual(len(lock["projects"]), 25)
        for item in lock["projects"]:
            self.assertRegex(item["revision"], r"^[0-9a-f]{40}$")

    def test_config_keeps_stock_cfi_and_modversions(self):
        p = profile()
        values = config_values(ROOT / p["config"])
        self.assertEqual(values["CONFIG_CFI_CLANG"], "y")
        self.assertEqual(values["CONFIG_MODVERSIONS"], "y")
        self.assertEqual(values["CONFIG_KPROBES"], "n")

    def test_symvers_rejects_conflicting_crcs(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "Module.symvers"
            f.write_text("0x00000001 x vmlinux\n0x00000002 x vmlinux\n")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                symvers(f)

    def test_artifact_abi_flag_cannot_hide_crc_change(self):
        p = profile()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {name: b"test" for name in ("Image.lz4", "kernel.config", "baseline.config", "System.map", "abi-report.json")}
            files.update({"Module.symvers": b"0x00000002 x vmlinux\n",
                          "baseline.Module.symvers": b"0x00000001 x vmlinux\n"})
            for name, data in files.items():
                (root / name).write_bytes(data)
            info = {"schema_version": 1, "profile": p, "abi_compatible": True,
                    "kernel_release": p["kernel_release"],
                    "files": {name: digest(root / name) for name in files}}
            (root / "build-info.json").write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "ABI"):
                check_artifact(root, p)

    def test_packer_stops_before_output_for_wrong_stock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "stock-boot.img").write_bytes(boot_image())
            with patch("pack_boot.check_artifact", return_value={}):
                with self.assertRaisesRegex(ValueError, "Wrong factory"):
                    pack(root, root, root / "output", profile())
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()

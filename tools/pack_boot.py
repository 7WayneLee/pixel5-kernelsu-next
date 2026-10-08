"""Pack a local stock boot only after checking stock module import CRCs."""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path

from common import (PROFILE_ID, artifact_file_names, boot_parts, compare_abi, cpio_entries, digest,
                    module_versions, profile, replace_kernel, symvers)
from avb_boot import regenerate_footer


def check_artifact(artifact: Path, p: dict) -> dict:
    info = json.loads((artifact / "build-info.json").read_text())
    if info.get("schema_version") != 1 or info.get("profile") != p:
        raise ValueError("Artifact was built for a different profile")
    required = set(artifact_file_names(p))
    if set(info.get("files", {})) != required:
        raise ValueError("Artifact file manifest is incomplete or unexpected")
    for name, expected in info["files"].items():
        if digest(artifact / name) != expected:
            raise ValueError(f"Artifact checksum mismatch: {name}")
    abi = compare_abi(symvers(artifact / "baseline.Module.symvers"),
                      symvers(artifact / "Module.symvers"))
    if not abi["compatible"] or info.get("abi_compatible") is not True:
        raise ValueError("Module ABI is incompatible; cannot retain stock vendor modules")
    if info.get("kernel_release") != p["kernel_release"]:
        raise ValueError("Kernel release mismatch")
    return info


def check_vendor_modules(vendor: bytes, symbols: dict[str, str], p: dict) -> int:
    if len(vendor) < 4096 or vendor[:8] != b"VNDRBOOT":
        raise ValueError("Not a vendor_boot image")
    version, page_size = struct.unpack_from("<II", vendor, 8)
    ramdisk_size = struct.unpack_from("<I", vendor, 24)[0]
    if version != 3 or page_size != 4096 or page_size + ramdisk_size > len(vendor):
        raise ValueError("Unexpected vendor_boot header")
    if not shutil.which("lz4"):
        raise ValueError("lz4 is required: macOS 'brew install lz4'; Linux 'sudo apt install lz4'")
    decoded = subprocess.run(["lz4", "-d", "-c"],
                             input=vendor[page_size:page_size + ramdisk_size],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    count, mismatches = 0, []
    for name, data in cpio_entries(decoded):
        if not name.endswith(".ko"):
            continue
        imports, release = module_versions(data)
        if release != p["kernel_release"]:
            raise ValueError(f"Stock module kernel release differs: {name}")
        count += 1
        for symbol, expected in imports.items():
            if symbols.get(symbol) != expected:
                mismatches.append({"module": name, "symbol": symbol,
                                   "stock_crc": expected, "built_crc": symbols.get(symbol)})
    if not count:
        raise ValueError("No stock modules found; ABI check cannot be skipped")
    if mismatches:
        raise ValueError(f"Stock module CRC mismatches ({len(mismatches)}): {mismatches[:12]}")
    return count


def pack(stock_dir: Path, artifact: Path, output: Path, p: dict) -> dict:
    info = check_artifact(artifact, p)
    boot_path, vendor_path = stock_dir / "stock-boot.img", stock_dir / "stock-vendor_boot.img"
    for path, key in ((boot_path, "stock_boot_sha256"), (vendor_path, "stock_vendor_boot_sha256")):
        if digest(path) != p[key]:
            raise ValueError(f"Wrong factory image or damaged file: {path.name}; expected {p['firmware']}")
    stock = boot_path.read_bytes()
    if len(stock) != p["boot_partition_size"]:
        raise ValueError("Stock boot partition size mismatch")
    count = check_vendor_modules(vendor_path.read_bytes(), symvers(artifact / "Module.symvers"), p)
    kernel = (artifact / "Image.lz4").read_bytes()
    patched, avb_report = regenerate_footer(boot_path, replace_kernel(stock, kernel))
    new_kernel, new_ramdisk = boot_parts(patched)
    if new_kernel != kernel or new_ramdisk != boot_parts(stock)[1]:
        raise ValueError("Boot round-trip verification failed")
    output.mkdir(parents=True, exist_ok=False)
    name = f"boot-{p['id']}-ksun.img"
    target = output / name
    target.write_bytes(patched)
    report = {"profile": p["id"], "firmware": p["firmware"], "output": name,
              "sha256": digest(target), "stock_boot_sha256": p["stock_boot_sha256"],
              "stock_module_count_checked": count, "ramdisk_preserved": True,
              "vendor_boot_preserved": True, "original_avb_metadata_removed": True,
              "hardware_tested": info.get("hardware_tested", False), **avb_report}
    (output / "packing-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "SHA256SUMS.txt").write_text(f"{report['sha256']}  {name}\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=PROFILE_ID)
    parser.add_argument("--stock-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(pack(args.stock_dir.resolve(), args.artifact_dir.resolve(),
                              args.output_dir.resolve(), profile(args.profile)), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Packing stopped: {error}\n")

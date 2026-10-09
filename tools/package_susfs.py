"""Package a version-matched, mountless SUSFS setup module after ABI validation."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from common import digest, profile
from pack_boot import check_artifact
from susfs import sources


def package(artifact: Path, output: Path, p: dict):
    if "susfs" not in p:
        raise ValueError("A SUSFS kernel profile is required")
    info = check_artifact(artifact, p)
    directory, lock = sources(p)
    if json.loads((artifact / "susfs-source-lock.json").read_text()) != lock:
        raise ValueError("Artifact SUSFS source lock differs from the project")
    module_prop = f'''id=pixel5_susfs
name=Pixel 5 SUSFS (KernelSU Next)
version=v1.5.5-pixel5
versionCode=15501
author=Pixel 5 KernelSU Next Builder
description=Stock Android 14 B2; SUSFS 1.5.5 NON-GKI. No mounts, SUS_SU or attestation credentials.
'''
    customize = '''#!/system/bin/sh
[ "$KSU" = true ] || abort "KernelSU Next is required"
[ "$(getprop ro.product.device)" = redfin ] || abort "Pixel 5 / redfin only"
chmod 755 "$MODPATH/ksu_susfs"
[ "$("$MODPATH/ksu_susfs" show version)" = v1.5.5 ] || abort "Boot the matching SUSFS 1.5.5 kernel first"
ui_print "SUSFS 1.5.5 NON-GKI verified"
ui_print "Reboot to apply path hiding and stock uname"
touch "$MODPATH/skip_mount"
'''
    post_fs = f'''#!/system/bin/sh
MODDIR=${{0%/*}}
BIN="$MODDIR/ksu_susfs"
STATUS="$MODDIR/status.txt"
if [ "$("$BIN" show version)" != v1.5.5 ]; then
  echo "Matching SUSFS kernel is not running; configuration skipped" > "$STATUS"
  exit 0
fi
"$BIN" enable_log 0
"$BIN" set_uname '{p['kernel_release']}' '#1 SMP PREEMPT Thu Sep 7 05:43:03 UTC 2023'
if [ -d /data/adb ]; then
  "$BIN" add_sus_path /data/adb
fi
echo "SUSFS v1.5.5: stock uname and /data/adb path hiding applied" > "$STATUS"
'''
    # There are no demo mount rules, property edits, downloaded credentials,
    # package hiding rules or modifications to any other module.
    entries = {
        "module.prop": module_prop.encode(),
        "customize.sh": customize.encode(),
        "post-fs-data.sh": post_fs.encode(),
        "skip_mount": b"",
        "ksu_susfs": (artifact / "ksu_susfs_arm64").read_bytes(),
        "LICENSE": (directory / "LICENSE").read_bytes(),
        "source/main.c": (directory / "ksu_susfs/jni/main.c").read_bytes(),
        "source/susfs.lock.json": json.dumps(lock, indent=2).encode() + b"\n",
        "source/build-info.json": json.dumps(info, indent=2).encode() + b"\n",
        "source/README.txt": b"Source and static-build adapter: https://github.com/7WayneLee/pixel5-kernelsu-next\nBuild adapters: tools/susfs.py and tools/package_susfs.py\nThis module requires the matching patched kernel and does not guarantee app compatibility.\n",
    }
    # Never replace an existing deliverable or create an output for a bad ABI.
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            item = zipfile.ZipInfo(name, (2023, 11, 5, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (0o100755 if name in ("ksu_susfs", "customize.sh", "post-fs-data.sh") else 0o100644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
    return {"profile": p["id"], "file": output.name, "sha256": digest(output),
            "susfs_version": lock["version"], "mountless": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="redfin-up1a-231105-001-b2-susfs")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.artifact_dir, args.output, profile(args.profile)), indent=2))

"""Verify and integrate the vendored, immutable SUSFS 4.19 sources."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from common import ROOT, config_values, digest


def sources(p: dict) -> tuple[Path, dict]:
    settings = p["susfs"]
    lock = json.loads((ROOT / settings["source_lock"]).read_text())
    if (lock["revision"] != settings["revision"] or
            not re.fullmatch(r"[0-9a-f]{40}", lock["revision"]) or
            lock["version"] != "v1.5.5" or lock["variant"] != "NON-GKI"):
        raise ValueError("Unexpected SUSFS source revision or variant")
    directory = (ROOT / lock["directory"]).resolve()
    if not directory.is_relative_to(ROOT.resolve()):
        raise ValueError("SUSFS source directory escapes the project")
    required = {"LICENSE", "kernel_patches/50_add_susfs_in_kernel-4.19.patch",
                "kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch",
                "kernel_patches/fs/susfs.c", "kernel_patches/include/linux/susfs.h",
                "kernel_patches/include/linux/susfs_def.h", "ksu_susfs/jni/main.c"}
    if set(lock["files"]) != required:
        raise ValueError("Incomplete SUSFS source manifest")
    for name, expected in lock["files"].items():
        if digest(directory / name) != expected:
            raise ValueError(f"SUSFS source checksum mismatch: {name}")
    return directory, lock


def config(p: dict) -> str:
    path = ROOT / p["susfs"]["config"]
    values = config_values(path)
    if values.get("CONFIG_KSU_SUSFS") != "y" or any(
            not key.startswith("CONFIG_KSU_SUSFS") for key in values):
        raise ValueError("SUSFS fragment may only configure SUSFS features")
    if values.get("CONFIG_KSU_SUSFS_SUS_SU", "n") != "n":
        raise ValueError("SUS_SU is unsupported on this NON-GKI profile")
    return path.read_text()


def integrate(kernel: Path, next_root: Path, p: dict, run):
    directory, _ = sources(p)
    for target, patch in (
        (kernel, directory / "kernel_patches/50_add_susfs_in_kernel-4.19.patch"),
        (next_root, ROOT / "patches/0003-next-susfs-4.19.patch"),
        (kernel, ROOT / "patches/0004-susfs-prctl.patch"),
        (kernel, ROOT / "patches/0005-susfs-next-symbols.patch"),
    ):
        run(["git", "-C", str(target), "apply", "--check", str(patch)])
        run(["git", "-C", str(target), "apply", str(patch)])
    for name in ("fs/susfs.c", "include/linux/susfs.h", "include/linux/susfs_def.h"):
        shutil.copyfile(directory / "kernel_patches" / name, kernel / name)


def build_tool(p: dict, output: Path, run):
    directory, _ = sources(p)
    # The upstream Android logging header is unused. Build a standalone Linux
    # arm64 executable; it needs no libraries from the Android installation.
    text = (directory / "ksu_susfs/jni/main.c").read_text()
    if text.count("#include <android/log.h>") != 1:
        raise ValueError("Unexpected SUSFS tool logging include")
    text = text.replace("#include <android/log.h>", "#include <limits.h> /* Static Linux build; Android logging is unused. */")
    old = "\tbool                    is_statically;"
    if text.count(old) != 1:
        raise ValueError("Unexpected SUSFS kstat command payload")
    # The kernel's command ABI declares this member as int, not bool. Avoid
    # interpreting uninitialized struct padding as part of a false value.
    text = text.replace(old, "\tint                     is_statically;")
    source = output / "ksu_susfs-build.c"
    source.write_text(text)
    run(["aarch64-linux-gnu-gcc", "-static", "-O2", "-Wall", "-Wextra",
         "-Wno-unused-parameter", "-Dst_atime_nsec=st_atim.tv_nsec",
         "-Dst_mtime_nsec=st_mtim.tv_nsec", "-Dst_ctime_nsec=st_ctim.tv_nsec",
         "-Dst_atimensec=st_atim.tv_nsec", "-Dst_mtimensec=st_mtim.tv_nsec",
         "-Dst_ctimensec=st_ctim.tv_nsec",
         str(source), "-o", str(output / "ksu_susfs_arm64")])
    run(["aarch64-linux-gnu-strip", str(output / "ksu_susfs_arm64")])
    shutil.copyfile(ROOT / p["susfs"]["source_lock"], output / "susfs-source-lock.json")

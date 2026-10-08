"""Build stock baseline, then KernelSU Next, and compare exported symbol CRCs."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from common import (ROOT, PROFILE_ID, artifact_file_names, compare_abi,
                    config_values, digest, profile, symvers)


def run(args, cwd=None, env=None, log=None):
    if log is None:
        subprocess.run(args, cwd=cwd, env=env, check=True)
        return
    with log.open("w") as stream:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            print(line, end="", flush=True)
            stream.write(line)
        if proc.wait():
            raise subprocess.CalledProcessError(proc.returncode, args)


def integrate(kernel: Path, p: dict):
    next_root = kernel / "KernelSU-Next"
    next_root.mkdir()
    run(["git", "init", "--quiet", str(next_root)])
    run(["git", "-C", str(next_root), "remote", "add", "origin",
         "https://github.com/KernelSU-Next/KernelSU-Next.git"])
    run(["git", "-C", str(next_root), "fetch", "--depth=1", "origin", p["next_revision"]])
    run(["git", "-C", str(next_root), "checkout", "--quiet", "--detach", "FETCH_HEAD"])
    # Pin version metadata rather than allowing upstream Kbuild to fetch history.
    kbuild = next_root / "kernel/Kbuild"
    text = kbuild.read_text()
    old = "$(shell cd $(GIT_ROOT) && [ -f .git/shallow ] && $(LPATH) git fetch --unshallow 2>/dev/null || true)"
    if text.count(old) != 1:
        raise ValueError("Unexpected Next Kbuild; version hook needs review")
    kbuild.write_text(text.replace(old, "# History fetch disabled: version is pinned by the build profile."))
    for repository, patch in ((kernel, "0001-redfin-manual-hooks.patch"),
                              (next_root, "0002-next-preserve-stock-seccomp-abi.patch")):
        location = str(ROOT / "patches" / patch)
        run(["git", "-C", str(repository), "apply", "--check", location])
        run(["git", "-C", str(repository), "apply", location])
    (kernel / "drivers/kernelsu").symlink_to("../KernelSU-Next/kernel")
    with (kernel / "drivers/Makefile").open("a") as stream:
        stream.write("\nobj-$(CONFIG_KSU) += kernelsu/\n")
    with (kernel / "drivers/Kconfig").open("a") as stream:
        stream.write('\nsource "drivers/kernelsu/Kconfig"\n')
    if "susfs" in p:
        from susfs import integrate as integrate_susfs
        integrate_susfs(kernel, next_root, p, run)


def build(workspace: Path, output: Path, p: dict, jobs: int):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Kernel compilation requires Linux x86_64; use GitHub Actions")
    output.mkdir(parents=True, exist_ok=False)
    if "susfs" in p:
        from susfs import build_tool
        build_tool(p, output, run)
    sources = workspace / "sources"
    kernel = sources / "private/msm-google"
    lock = json.loads((ROOT / p["source_lock"]).read_text())
    for item in lock["projects"]:
        actual = subprocess.check_output(["git", "-C", str(sources / item["path"]),
                                          "rev-parse", "HEAD"], text=True).strip()
        if actual != item["revision"]:
            raise ValueError(f"Wrong source revision: {item['path']}")
    shutil.copyfile(ROOT / p["config"], kernel / "arch/arm64/configs/pixel5_ci_defconfig")
    (kernel / ".scmversion").write_text(p["scmversion"] + "\n")
    (sources / "pixel5-ci.config").write_text('''KERNEL_DIR=private/msm-google
BUILD_BOOT_IMG=""
. ${ROOT_DIR}/${KERNEL_DIR}/build.config.redbull.common.clang
DEFCONFIG=pixel5_ci_defconfig
POST_DEFCONFIG_CMDS=""
KMI_SYMBOL_LIST=android/abi_gki_aarch64_redbull
TRIM_NONLISTED_KMI=1
BUILD_BOOT_IMG=""
BUILD_VENDOR_BOOT_IMG=""
BUILD_INITRAMFS=1
LZ4_RAMDISK=1
COMPRESS_UNSTRIPPED_MODULES=0
UNSTRIPPED_MODULES=""
MAKE_GOALS="Image.lz4 modules"
FILES="arch/arm64/boot/Image.lz4 vmlinux System.map .config Module.symvers"
''')
    env = os.environ.copy()
    env.update(BUILD_CONFIG="pixel5-ci.config", OUT_DIR=str(workspace / "out"),
               DIST_DIR=str(workspace / "dist"), SKIP_MRPROPER="1")
    command = ["bash", "build/build.sh", f"-j{jobs}"]
    run(command, sources, env, output / "baseline-build.log")
    dist = workspace / "dist"
    stock_config = config_values(dist / ".config")
    baseline = output / "baseline.Module.symvers"
    shutil.copyfile(dist / "Module.symvers", baseline)
    shutil.copyfile(dist / ".config", output / "baseline.config")
    integrate(kernel, p)
    with (kernel / "arch/arm64/configs/pixel5_ci_defconfig").open("a") as stream:
        stream.write("\nCONFIG_KSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n# CONFIG_KSU_KPROBES_HOOK is not set\n# CONFIG_KSU_SYSCALL_TABLE_HOOK is not set\n")
        if "susfs" in p:
            from susfs import config
            stream.write(config(p))
    run(command + [f"KSU_VERSION_OVERRIDE={p['next_version']}",
                   f"KSU_VERSION_TAG_OVERRIDE={p['next_version_tag']}"],
        sources, env, output / "next-build.log")
    actual_config = config_values(dist / ".config")
    if actual_config.get("CONFIG_KSU") != "y" or actual_config.get("CONFIG_KSU_MANUAL_HOOK") != "y":
        raise ValueError("Next did not remain built-in with manual hooks")
    if "susfs" in p:
        from susfs import config
        expected_susfs = config_values(ROOT / p["susfs"]["config"])
        if any(actual_config.get(key, "n") != value for key, value in expected_susfs.items()):
            raise ValueError("SUSFS features differ from the pinned profile")
    drift = {key: [value, actual_config.get(key)] for key, value in stock_config.items()
             if not key.startswith("CONFIG_KSU") and actual_config.get(key) != value}
    if drift:
        raise ValueError(f"Stock config changed unexpectedly: {drift}")
    for key in ("CONFIG_CFI_CLANG", "CONFIG_MODVERSIONS", "CONFIG_LTO_CLANG"):
        if actual_config.get(key) != "y":
            raise ValueError(f"Stock safety/ABI config was lost: {key}")
    shutil.copyfile(dist / "Image.lz4", output / "Image.lz4")
    shutil.copyfile(dist / "Module.symvers", output / "Module.symvers")
    shutil.copyfile(dist / ".config", output / "kernel.config")
    shutil.copyfile(dist / "System.map", output / "System.map")
    # All baseline exported symbols must retain their CRCs. New KSU exports are OK.
    abi = compare_abi(symvers(baseline), symvers(output / "Module.symvers"))
    (output / "abi-report.json").write_text(json.dumps(abi, indent=2) + "\n")
    release = (workspace / "out/private/msm-google/include/config/kernel.release").read_text().strip()
    if release != p["kernel_release"]:
        raise ValueError(f"Kernel release differs from stock modules: {release}")
    metadata = {"schema_version": 1, "profile": p, "kernel_release": release,
                "abi_compatible": abi["compatible"], "hardware_tested": False,
                "files": {name: digest(output / name) for name in artifact_file_names(p)}}
    (output / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n")
    shutil.copyfile(ROOT / p["source_lock"], output / "source-lock.json")
    checksum = "".join(f"{digest(f)}  {f.name}\n" for f in sorted(output.iterdir()) if f.is_file())
    (output / "SHA256SUMS.txt").write_text(checksum)
    if not abi["compatible"]:
        raise ValueError("Module ABI changed. Artifacts are diagnostic only; local boot packing is blocked.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=PROFILE_ID)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=2)
    args = parser.parse_args()
    build(args.workspace.resolve(), args.output.resolve(), profile(args.profile), args.jobs)

# Pixel 5 KernelSU Next Builder

[![Tooling CI](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/workflows/ci.yml/badge.svg)](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/workflows/ci.yml)

[繁體中文](README.md)

The [first successful build](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741524948) compiled stock and Next, retained all 9,115 exported symbol CRCs, and passed local checks against 218 stock vendor_boot modules. Hardware boot and root remain untested.

Build a KernelSU Next kernel for **Google Pixel 5 (redfin), stock Android 14 UP1A.231105.001.B2**, using GitHub Actions. Pack the kernel into your own factory boot image locally.

**Experimental: hardware boot and root validation have not been completed. A successful workflow confirms compilation and static checks only.** See [validation status](docs/validation.md).

## Build

1. Fork this repository and enable Actions in your fork.
2. Run **Build Pixel 5 KernelSU Next** with the `redfin-up1a-231105-001-b2` profile.
3. Download and extract the artifact from a successful run.

The workflow builds the stock baseline before integrating the pinned Next legacy commit, manual hooks, and the ABI-preservation patch. It retains stock CFI, LTO, and MODVERSIONS. Original exported symbol CRCs must match. Failed builds may upload diagnostic artifacts; these are not usable kernel releases.

## Pack locally

Install Python 3.11+ and `lz4` (macOS: `brew install lz4`; Linux: `sudo apt install lz4`). Obtain the exact factory firmware from [Google](https://developers.google.com/android/images#redfin). Copy `boot.img` and `vendor_boot.img` to a directory and name them `stock-boot.img` and `stock-vendor_boot.img`.

```bash
python3 tools/pack_boot.py \
  --stock-dir /path/to/stock-boot \
  --artifact-dir /path/to/extracted-artifact \
  --output-dir /path/to/new-output-directory
```

The packer verifies stock image hashes, artifact hashes, baseline ABI comparison, and the import CRCs and vermagic of every module in stock vendor_boot. It stops on any mismatch. It replaces only the boot kernel, preserves the stock boot ramdisk, and removes obsolete boot AVB metadata. Stock vendor_boot, its DTB, and dtbo remain unchanged. An already-unlocked bootloader is required. Factory images are neither uploaded nor distributed by this project.

## Test before flashing

Install the [official Next Manager v3.4.0](https://github.com/KernelSU-Next/KernelSU-Next/releases/tag/v3.4.0). Keep your factory boot backup. Verify the product is redfin, note the active slot, and test a temporary boot:

```bash
adb reboot bootloader
fastboot getvar product
fastboot getvar current-slot
fastboot boot /path/to/boot-redfin-up1a-231105-001-b2-ksun.img
```

Check root permissions, Wi-Fi, cellular, camera, touch, audio, Bluetooth, and reboot behavior. Do not permanently flash until these checks pass. A failed temporary boot can be recovered by returning to the bootloader and rebooting the unchanged stock image.

After testing, return to the bootloader, verify the active slot again, then run `fastboot flash boot /path/to/patched.img` and `fastboot reboot`. To restore, flash your original `stock-boot.img` to that same slot. No data wipe or bootloader relock is part of this procedure.

Only the listed Pixel 5 firmware is supported. Pixel 4a 5G, Pixel 5a, custom ROMs, and different firmware need separate source/config/image profiles and validation. This project does not include SUSFS or automate flashing.

## Maintenance

Google sources and Next are locked to immutable commits. The local patches include manual read, exec, stat, reboot and input hooks, and avoid an unused seccomp struct backport that would change stock module ABI. Review those assumptions when updating Next. See [development notes](docs/development.md) and [licensing](NOTICE.md).

Run tooling tests with `python3 -m unittest discover -s tests -v`. Reports should include a workflow URL, firmware version and relevant validation report, without credentials or personal data.

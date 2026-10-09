# Pixel 5 KernelSU Next Builder

[正體中文](README.zh-TW.md)

Build a KernelSU Next kernel for Pixel 5 using GitHub Actions.

## Supported configuration

| Item | Supported configuration |
| --- | --- |
| Device | Google Pixel 5 (`redfin`) |
| OS | Google stock Android 14 |
| Firmware | `UP1A.231105.001.B2` |
| Kernel | `4.19.278-g7b0944645172-ab10812814` |
| KernelSU Next | `v3.4.0-legacy-pixel5` · 33306 · UAPI 5 |
| Manager | [v3.4.0-29-g3daa5787](https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/37513294225) · 33323 · UAPI 5 |
| Integration | Built-in, manual hooks; stock CFI/LTO/MODVERSIONS retained |
| Optional SUSFS | v1.5.5 NON-GKI / kernel-4.19; experimental profile, boot and basic hiding verified on one device ([record](docs/susfs-validation.md)) |
| Bootloader | Unlocked |
| Validation | Boot and ADB root verified on one device; full hardware testing pending ([record](docs/validation.md)) |

**Manager compatibility:** use the linked, verified UAPI 5 build. Sign in to GitHub and download its `manager` artifact. The v3.4.0 release APK (33294, UAPI 4) is incompatible with this kernel.

Only the device and stock firmware listed above are supported. Exact source versions are recorded in the [kernel profile](profiles/redfin-up1a-231105-001-b2.json) and [Manager lock](sources/manager.lock.json).

## GitHub Actions

1. Fork this repository and enable **Actions** in your fork.
2. Open **Actions → Build Pixel 5 KernelSU Next → Run workflow**.
3. Select `redfin-up1a-231105-001-b2` for the verified kernel, or `redfin-up1a-231105-001-b2-susfs` for the experimental SUSFS kernel, and start the workflow.
4. Wait for the build and ABI checks to succeed.
5. Open the successful run and download `pixel5-<profile>-<run_number>` from **Artifacts**, matching the selected profile.

The artifact contains `Image.lz4`, ABI reports, build metadata and logs. Artifacts from failed runs are for diagnostics only.

Leave `baseline_run_id` empty for a fresh stock baseline. An earlier successful standard-profile run in your fork can be reused only after source, checksum and stock-config validation; all stock export CRCs are still compared.

The SUSFS artifact also includes `ksu_susfs_arm64`, its source lock, and `pixel5-susfs-module-v1.5.5.zip`. Install this mountless module only after booting the matching SUSFS kernel. SUS_SU and automatic overlayfs spoofing are disabled. SUSFS does not guarantee that every app will accept a rooted or unlocked device.

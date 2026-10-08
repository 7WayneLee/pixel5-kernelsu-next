# Validation status

Target: Pixel 5 redfin, stock Android 14 UP1A.231105.001.B2.

| Check | Status |
| --- | --- |
| Factory boot and vendor_boot hashes/fingerprint | Checked against the supplied stock images |
| Stock kernel config extraction | Completed |
| Compiled baseline config compared with stock | Identical except for the relocated symbol-whitelist path; no additional options |
| Google kernel commit and 25-repository source lock | Checked |
| Manual hooks and ABI patch apply to pinned sources | Checked locally |
| Python tooling tests | 23 passed locally and in [GitHub CI](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37770707349), including AVB signature/hash verification, property preservation, tampering and capacity checks |
| GitHub Actions YAML validation | Passed with actionlint 1.7.12 |
| Real stock ELF parsing and boot repack round trip | 218 modules / 2642 import CRCs parsed; original boot payload preserved |
| GitHub-hosted full stock and Next compilation | [Workflow run #2](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741524948) succeeded on 2026-10-08; job duration 51m32s |
| Baseline-to-Next exported symbol CRCs | All 9,115 identical; none changed or removed |
| Stock module import CRC verification against built kernel | All 218 vendor_boot modules passed, covering 2,642 distinct imported symbols |
| Local patched boot creation | Completed; stock ramdisk preserved; original images unchanged |
| Temporary boot | Passed on a Pixel 5 on 2026-10-08 |
| Running kernel identity | /proc/config.gz exactly matches the compiled Next config; CONFIG_KSU=y and CONFIG_KSU_MANUAL_HOOK=y |
| Next Manager | Official CI Manager 33323 / UAPI 5 installed; displays Working, kernel 33306-5 and Manual hooks; APK signing certificate matches the kernel's expected certificate |
| Root authorization | Passed after the user authorized Shell in Manager: su -c id returned uid=0(root), and whoami returned root; SELinux remained Enforcing |
| Android services and modules | Android boot completed, SELinux Enforcing, 328 loaded modules; Wi-Fi, phone, camera, audio, Bluetooth and input services found after permanent boot |
| Physical cellular, Wi-Fi, camera, audio, Bluetooth, touch functions | Not tested; service presence does not verify hardware operation |
| Permanent flashing | boot_a write returned OKAY; normal reboot reached Android and remained running for at least 10 minutes |
| AVB footer | Regenerated and signature/hash verified; repaired packer reproduces the exact flashed image |

Do not turn a successful compile into a hardware compatibility claim. Add a workflow run URL and the actual device checks when updating this record.

The first workflow attempt identified a stock config whitelist path that referred to Google's internal build server. The builder now generates that whitelist from the pinned redbull source list into the current output directory; symbol trimming remains enabled.

The first local pack removed the old AVB footer. Although temporary boot worked, normal boot after flashing returned to the bootloader. Regenerating the footer with a valid payload hash, the stock rollback index (1699142400), all stock properties and Google's public test signing key resolved this on the tested unlocked device. The packer now always verifies this footer before exporting an image. No vendor_boot, dtbo or vbmeta flashing was needed.

Verified output from workflow #2 and the corrected local packer:

```text
Image.lz4 SHA-256:
8c3387fd89a1a908ddc009af1530aa66141e2f3f4e6a1c5f3aef1c6cc0ad3a77

Locally packed boot-redfin-up1a-231105-001-b2-ksun.img SHA-256:
b30b733d9e0a94e4d5f3a761fc0634e3b4e0de54a1b4571e124f19236b3a3b61
```

These hashes identify this run's outputs. Future builds may produce different image hashes because kernel build timestamps change. Always use the checksum generated alongside your own artifact or packed boot.

Running Next config SHA-256 (exact byte match with the artifact):

```text
2b7d818c13d4231feaf44f283c23f89413a81fed77c853c7e2bb987a3f3a5756
```

The release string intentionally matches stock, so `uname -r` alone cannot establish that Next is running. The config comparison supplies separate evidence. Root privileges were separately verified with `adb shell su -c id` after Manager compatibility was corrected and Shell was authorized.

The initial release Manager 33294 used UAPI 4 and displayed a version-too-old warning for this UAPI 5 kernel. Updating to the official signed [Manager CI artifact](https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/37513294225) (33323, UAPI 5) removed that warning and enabled the Superuser page. Its archive SHA-256 and APK certificate were checked before installation. The exact provenance is recorded in `sources/manager.lock.json`.

Verified root command output on 2026-10-08:

```text
$ adb shell su -c id
uid=0(root) gid=0(root) groups=0(root) context=u:r:ksu:s0
$ adb shell su -c whoami
root
```

Android boot remained completed and SELinux remained Enforcing. No physical camera, cellular, Bluetooth, audio or touch functionality claim is inferred from root success.

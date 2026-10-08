# Validation status

Target: Pixel 5 redfin, stock Android 14 UP1A.231105.001.B2.

| Check | Status |
| --- | --- |
| Factory boot and vendor_boot hashes/fingerprint | Checked against the supplied stock images |
| Stock kernel config extraction | Completed |
| Compiled baseline config compared with stock | Identical except for the relocated symbol-whitelist path; no additional options |
| Google kernel commit and 25-repository source lock | Checked |
| Manual hooks and ABI patch apply to pinned sources | Checked locally |
| Python tooling tests | 19 passed locally and in [GitHub CI](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741497541) |
| GitHub Actions YAML validation | Passed with actionlint 1.7.12 |
| Real stock ELF parsing and boot repack round trip | 218 modules / 2642 import CRCs parsed; original boot payload preserved |
| GitHub-hosted full stock and Next compilation | [Workflow run #2](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741524948) succeeded on 2026-10-08; job duration 51m32s |
| Baseline-to-Next exported symbol CRCs | All 9,115 identical; none changed or removed |
| Stock module import CRC verification against built kernel | All 218 vendor_boot modules passed, covering 2,642 distinct imported symbols |
| Local patched boot creation | Completed; stock ramdisk preserved; original images unchanged |
| Temporary boot, Next Manager and root | Not tested on hardware |
| Cellular, Wi-Fi, camera, audio, Bluetooth, touch | Not tested on hardware |
| Permanent flashing | Not performed |

Do not turn a successful compile into a hardware compatibility claim. Add a workflow run URL and the actual device checks when updating this record.

The first workflow attempt identified a stock config whitelist path that referred to Google's internal build server. The builder now generates that whitelist from the pinned redbull source list into the current output directory; symbol trimming remains enabled.

Verified output from workflow #2:

```text
Image.lz4 SHA-256:
8c3387fd89a1a908ddc009af1530aa66141e2f3f4e6a1c5f3aef1c6cc0ad3a77

Locally packed boot-redfin-up1a-231105-001-b2-ksun.img SHA-256:
50aa409cf4be57c46f5c7494b28181a31f7cea8d57debbe883f27b0f9105669d
```

These hashes identify this run's outputs. Future builds may produce different image hashes because kernel build timestamps change. Always use the checksum generated alongside your own artifact or packed boot.

# Validation status

Target: Pixel 5 redfin, stock Android 14 UP1A.231105.001.B2.

| Check | Status |
| --- | --- |
| Factory boot and vendor_boot hashes/fingerprint | Checked against the supplied stock images |
| Stock kernel config extraction | Completed |
| Google kernel commit and 25-repository source lock | Checked |
| Manual hooks and ABI patch apply to pinned sources | Checked locally |
| Python tooling tests | 19 passed locally |
| GitHub Actions YAML validation | Passed with actionlint 1.7.12 |
| Real stock ELF parsing and boot repack round trip | 218 modules / 2642 import CRCs parsed; original boot payload preserved |
| GitHub-hosted full stock and Next compilation | Pending first workflow run |
| Stock module import CRC verification against built kernel | Requires successful build artifacts |
| Temporary boot, Next Manager and root | Not tested on hardware |
| Cellular, Wi-Fi, camera, audio, Bluetooth, touch | Not tested on hardware |
| Permanent flashing | Not performed |

Do not turn a successful compile into a hardware compatibility claim. Add a workflow run URL and the actual device checks when updating this record.

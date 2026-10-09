# SUSFS validation

Tested on one Pixel 5 (`redfin`), Google stock Android 14
`UP1A.231105.001.B2`, on 2026-10-09.

[Build run #8](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37894232445)
completed successfully in 36m34s using builder commit
`70981731e295909afc5d52e28cc5f0015e3208a9` and the
`redfin-up1a-231105-001-b2-susfs` profile.

| Check | Result |
| --- | --- |
| SUSFS source | `kernel-4.19`, commit `001e69919c6271f690fd00b17e4c721c9e599152`, v1.5.5 NON-GKI |
| Next / Manager | Kernel 33306 / UAPI 5; existing official Manager 33323 / UAPI 5 retained; module installation passed the userspace UAPI check |
| Tooling | 29 Python tests passed; both workflow files passed actionlint |
| Stock baseline | Reused the checksum-verified baseline from [run #2](https://github.com/7WayneLee/pixel5-kernelsu-next/actions/runs/37741524948), with identical pinned Google sources and stock config except for the relocated whitelist path |
| Exported symbol ABI | All 9,115 stock export CRCs unchanged; none removed |
| Stock vendor_boot modules | All 218 modules passed import CRC and kernel release checks |
| Boot packing | Stock ramdisk retained; AVB footer regenerated and signature/hash verified |
| Temporary boot | Passed twice before permanent flashing |
| Permanent boot | `boot_a` write returned OKAY; three normal reboots passed; partition SHA-256 exactly matches the tested image |
| Running kernel | `/proc/config.gz` exactly matches the artifact; stock CFI/LTO/MODVERSIONS remain enabled |
| Android / root | Boot completed, SELinux Enforcing, `su -c id` returned UID 0 in `u:r:ksu:s0` |
| Modules / services | 328 loaded modules; surfaceflinger, audioserver, cameraserver and both zygotes running |
| SUSFS control | Version v1.5.5, variant NON-GKI, feature mask 8159; invalid reply/payload pointers rejected |
| Control authorization | UID 2000 and test app UID 19990 denied; status sentinel and output buffer unchanged |
| Path hiding | Test UID 19990 initially saw both files; after adding one SUS_PATH rule, its stat returned ENOENT while the control file stayed visible |
| Mount hiding | Bind mount in a private test namespace absent from mountinfo, while the mounted file remained accessible; detached successfully |
| Symbol hiding | No `ksu_`, `kernelsu`, `susfs_` or `ksud` names found in `/proc/kallsyms` |
| Matching module | `pixel5_susfs`, v1.5.5-pixel5 installed; mountless; stock uname and `/data/adb` hiding configuration automatically reapplied after normal boot; deleting its status file and observing recreation confirmed the boot script ran |
| Cleanup | Test fixtures, binaries and installation ZIP removed from the phone; final reboot cleared volatile test rules |

The application test is a disposable native process with a private mount
namespace. It enters the zygote SELinux domain and drops to unused UID 19990
to exercise the credential hook. It does not read a real application's data
or prove acceptance by a specific third-party application.

A boot warning at `kernel/kthread.c:906`
(`__kthread_queue_delayed_work → kthread_mod_delayed_work → sde_encoder_resource_control [msm_drm]`)
was observed. Rebooting the previously flashed, non-SUSFS Next kernel reproduced
the same warning, with its running config matching the previous artifact.
No new kernel panic, CFI failure or module CRC error was observed during these
tests. The warning remains a limitation of the tested baseline; it was not
silenced or represented as fixed.

Physical cellular, Wi-Fi, camera, audio, Bluetooth and touch functions,
long-term stability, Play Integrity and acceptance by specific applications
were not tested. Other compiled SUSFS features were queried but not individually
exercised. SUS_SU and automatic overlayfs spoofing are disabled.

Hashes identifying this tested build:

```text
Image.lz4:
fc0a336bef7b0a02607033044feb4fe4b79663567f0a58443057be65051efde6

Running kernel.config:
b7cb555c0a353f5b489fe3184e19d5f911795f033ab6be83cffc9e8673340bd1

Locally packed boot (also verified directly on boot_a):
256de30d564a88b5425ce28c6a1e7e0b4d204be01f50e7e97be87f16db64a65c

pixel5-susfs-module-v1.5.5.zip:
4cf57f6ed09eb4900ddc3c8d852b5c5609aa2b075e1633d7a95ef8507445f408
```

These hashes identify this run. Use the manifest supplied with your own artifact
and boot pack. Factory images and the locally packed boot are not uploaded to
this repository.

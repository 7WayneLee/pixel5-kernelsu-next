# Development

Compilation uses Linux x86_64 and Google's pinned clang-r416183b toolchain. The packer also works on macOS. Use a new empty build workspace for each build.

Install the packages listed in `.github/workflows/build.yml`, then run from the project root:

```bash
python3 tools/sync_sources.py --workspace .work/sources --jobs 4
python3 tools/build.py --workspace .work --output artifacts --jobs 2
```

Plan for at least 30 GiB of free storage and enough memory for stock CFI/LTO linking; the exact peak has not yet been measured. The workflow frees preinstalled SDK directories on its disposable hosted runner. No cleanup command runs on users' machines.

`sync_sources.py` checks out the locked Google repositories in parent-before-child order and reproduces manifest linkfiles. The source workspace must be empty. It does not run upstream setup scripts from moving branches.

`build.py` first uses the config extracted from the exact stock boot, then integrates the pinned Next commit. The six Linux files patched are fs/exec.c, fs/open.c, fs/read_write.c, fs/stat.c, kernel/reboot.c, and drivers/input/input.c. The read hook matches the pinned `void ksu_handle_sys_read(unsigned int fd)` prototype, and the fstat return hook extends init.rc size for the injected daemon service. Exec hooks cover native execve/execveat and the shared compat entry point. The reboot hook allows the manager to obtain the driver descriptor. Input hooks provide Next safe mode support.

The kernel release string is kept equal to stock because vendor modules check vermagic. This is accompanied by independent symbol CRC checks; the release string alone is not evidence of compatibility. Baseline-to-Next comparison checks every baseline export, including symbols used by modules outside vendor_boot. Local packing additionally checks the real module imports in the user's stock vendor_boot.

Next's stock Kbuild backports SELinux accessors and path_umount. It also attempted to insert `filter_count` into struct seccomp. This profile keeps the stock 4.19 `put_seccomp_filter` path, where that counter is not used, so the accompanying patch omits the insertion. Do not apply this patch to newer kernels or a source tree that lacks `put_seccomp_filter`.

Build metadata pins the reported Next version to the commit count of the selected legacy commit (30000 + 3017 + 289 = 33306); no history fetch occurs during make. The version tag identifies the custom integration. The expected official manager signature remains unchanged.

If a compile or ABI check fails, inspect the log before changing flags. Disabling CFI, changing stock module structures, or overriding import CRC checks changes the compatibility contract and requires a different profile/deployment strategy.

When updating sources, regenerate the full source lock, config/image hashes and patches, run tooling CI, then perform full kernel compilation and device validation. Preserve the exact matching Next Manager version. Mark hardware status as untested until a real device has passed the published checks.

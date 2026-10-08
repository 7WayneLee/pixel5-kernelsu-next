# Sources and licensing

The original Python tooling, GitHub Actions workflows, and documentation in this repository are MIT licensed.

`configs/redfin-stock.config` is an extracted Linux configuration and is provided under GPL-2.0-only. The patches under `patches/` are derived from Linux and KernelSU Next kernel source and are GPL-2.0-only. They do not replace those projects' copyright notices or licenses.

Google kernel source: https://android.googlesource.com/kernel/msm/

Google build scripts and toolchains are fetched from the repositories and exact commits listed in `sources/google.lock.json`; they retain their upstream licenses.

KernelSU Next: https://github.com/KernelSU-Next/KernelSU-Next

KernelSU Next's kernel directory is GPL-2.0-only. Its remaining components have their own upstream licensing. Compiled kernel redistribution must comply with the kernel's GPL obligations; keep the exact source manifest, patches and config with the build metadata and make corresponding source available.

Google factory images and proprietary device files are not included or redistributed here. Users obtain their own images and pack them locally.

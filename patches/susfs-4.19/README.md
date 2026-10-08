Pinned verbatim sources from [SUSFS kernel-4.19](https://gitlab.com/simonpunk/susfs4ksu/-/tree/001e69919c6271f690fd00b17e4c721c9e599152), version 1.5.5 NON-GKI.

The upstream LICENSE is preserved. Every upstream file is SHA-256 checked against `sources/susfs.lock.json`. The old KernelSU patch is kept as a reference; it is **not** applied to Next. This project's separate adapter patches retain Next's UAPI 5, Manager authentication, manual hooks, and stock Android KABI reserves.

The static arm64 control tool is built from upstream `ksu_susfs/jni/main.c`; only its unused Android log include and libc timestamp member spelling are adjusted during compilation. SUS_SU is unsupported. No keybox or attestation credentials are included.

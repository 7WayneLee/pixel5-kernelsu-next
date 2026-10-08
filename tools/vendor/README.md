# Vendored AVB tooling

Source repository: https://android.googlesource.com/kernel/prebuilts/build-tools

Pinned commit: `ca5b087f88c0302ff66f59a6f26be663e92baf15` (also present in `sources/google.lock.json`).

| File | Upstream origin | SHA-256 |
| --- | --- | --- |
| avbtool.py | Python source extracted unchanged from the ZIP appended to linux-x86/bin/avbtool | 8b7afa9aad7326d2528903a87eb9e5a37ae22bf20b24a71037552ac0cb30ad98 |
| testkey_rsa2048.pem | linux-x86/share/avb/testkey_rsa2048.pem | f1d5765a2bdfb92fb08aee021107c7ac1a7a3f590dafd853771c85375ef0fbd7 |

The script reports avbtool 1.2.0 and retains its full upstream MIT copyright and license header. Only this script is extracted; embedded Python runtime libraries are not bundled.

The PEM file contains a publicly distributed **test private signing key**. Anyone can use this key; it supplies no OEM trust or production security. It is intentionally committed as an upstream test fixture, not a secret. This project uses it to regenerate structurally valid, verifiable boot AVB metadata on an already-unlocked device. Keep the bootloader unlocked while using this image.

No network download is required during local boot packing. Never substitute a personal or production private key in this directory or publish one to this repository.

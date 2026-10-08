"""Regenerate boot AVB metadata for an already-unlocked Pixel 5."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import boot_parts
from vendor import avbtool

VENDOR = Path(__file__).resolve().parent / "vendor"
AVBTOOL = VENDOR / "avbtool.py"
TEST_KEY = VENDOR / "testkey_rsa2048.pem"


def run_avb(*arguments: str) -> str:
    result = subprocess.run([sys.executable, str(AVBTOOL), *arguments],
                            text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f"AVB {arguments[0]} failed: {result.stderr.strip()}")
    return result.stdout


def read_metadata(path: Path) -> dict:
    """Read stock metadata without opening the user's image for writing."""
    image = avbtool.ImageHandler(str(path), read_only=True)
    try:
        footer, header, descriptors, size = avbtool.Avb()._parse_image(image)
        if footer is None or image.is_sparse or header.flags or header.rollback_index_location:
            raise ValueError("Unsupported stock boot AVB layout")
        hashes = [d for d in descriptors if isinstance(d, avbtool.AvbHashDescriptor)]
        props = [d for d in descriptors if isinstance(d, avbtool.AvbPropertyDescriptor)]
        if len(hashes) != 1 or len(hashes) + len(props) != len(descriptors):
            raise ValueError("Unexpected stock boot AVB descriptors")
        descriptor = hashes[0]
        if (descriptor.partition_name != "boot" or descriptor.hash_algorithm != "sha256"
                or descriptor.flags or descriptor.image_size != footer.original_image_size
                or not 0 < descriptor.image_size <= footer.vbmeta_offset < size - 64):
            raise ValueError("Unsupported stock boot hash descriptor")
        image.seek(0)
        hashed = hashlib.sha256(descriptor.salt + image.read(descriptor.image_size)).digest()
        if hashed != descriptor.digest:
            raise ValueError("Stock boot AVB payload hash mismatch")
        properties = [(d.key, d.value.decode("utf-8")) for d in props]
        if len({key for key, _ in properties}) != len(properties):
            raise ValueError("Duplicate stock boot AVB property")
        if any(":" in key or "\0" in key + value for key, value in properties):
            raise ValueError("Unsupported stock boot AVB property encoding")
        return {"partition_size": size, "rollback_index": header.rollback_index,
                "salt": descriptor.salt.hex(), "properties": properties}
    except (avbtool.AvbError, LookupError, UnicodeError) as error:
        raise ValueError(f"Invalid stock boot AVB metadata: {error}") from error
    finally:
        image._image.close()


def regenerate_footer(stock_path: Path, patched: bytes) -> tuple[bytes, dict]:
    if not shutil.which("openssl"):
        raise ValueError("openssl is required to sign and verify boot AVB metadata")
    metadata = read_metadata(stock_path)
    if len(patched) != metadata["partition_size"]:
        raise ValueError("Patched boot partition size mismatch")
    kernel, ramdisk = boot_parts(patched)
    payload_size = 4096 + ((len(kernel) + 4095) & ~4095) + ((len(ramdisk) + 4095) & ~4095)
    with tempfile.TemporaryDirectory(prefix="pixel5-avb-") as td:
        # verify_image resolves the hash descriptor's partition as boot.img.
        image = Path(td) / "boot.img"
        image.write_bytes(patched[:payload_size])
        arguments = ["add_hash_footer", "--image", str(image),
                     "--partition_name", "boot", "--partition_size", str(len(patched)),
                     "--algorithm", "SHA256_RSA2048", "--key", str(TEST_KEY),
                     "--rollback_index", str(metadata["rollback_index"]),
                     "--salt", metadata["salt"]]
        for key, value in metadata["properties"]:
            arguments.extend(["--prop", f"{key}:{value}"])
        run_avb(*arguments)
        run_avb("verify_image", "--image", str(image), "--key", str(TEST_KEY))
        result = image.read_bytes()
        if (len(result) != len(patched) or result[:payload_size] != patched[:payload_size]
                or read_metadata(image) != metadata):
            raise ValueError("AVB round-trip changed boot payload or stock properties")
    return result, {"avb_footer_regenerated": True, "avb_signature_verified": True,
                    "avb_signature_algorithm": "SHA256_RSA2048",
                    "avb_signing_key": "Google public test key; unlocked bootloader only",
                    "avb_rollback_index": metadata["rollback_index"],
                    "avb_properties": dict(metadata["properties"])}

"""Ensure version-matched setup modules remain mountless and fail closed."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from common import ROOT, artifact_file_names, digest, profile
from package_susfs import package


def artifact(directory, p, corrupt_lock=False):
    for name in artifact_file_names(p):
        (directory / name).write_bytes(b"fixture")
    for name in ("Module.symvers", "baseline.Module.symvers"):
        (directory / name).write_text("0x00000001 fixture vmlinux\n")
    lock = json.loads((ROOT / p["susfs"]["source_lock"]).read_text())
    if corrupt_lock:
        lock["revision"] = "0" * 40
    (directory / "susfs-source-lock.json").write_text(json.dumps(lock))
    info = {"schema_version": 1, "profile": p, "kernel_release": p["kernel_release"],
            "abi_compatible": True, "files": {name: digest(directory / name)
                                              for name in artifact_file_names(p)}}
    (directory / "build-info.json").write_text(json.dumps(info))


class ModulePackageTests(unittest.TestCase):
    def test_different_source_lock_is_rejected_before_writing_zip(self):
        p = profile("redfin-up1a-231105-001-b2-susfs")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact(root, p, corrupt_lock=True)
            target = root / "module.zip"
            with self.assertRaisesRegex(ValueError, "source lock"):
                package(root, target, p)
            self.assertFalse(target.exists())

    def test_generated_module_has_no_mount_payload_and_valid_shell(self):
        p = profile("redfin-up1a-231105-001-b2-susfs")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact(root, p)
            target = root / "module.zip"
            package(root, target, p)
            with zipfile.ZipFile(target) as archive:
                self.assertIn("skip_mount", archive.namelist())
                self.assertFalse(any(name.split("/")[0] in ("system", "vendor", "product", "system_ext")
                                     for name in archive.namelist()))
                for name in ("customize.sh", "post-fs-data.sh"):
                    subprocess.run(["sh", "-n"], input=archive.read(name), check=True)
                self.assertIn(b"show version", archive.read("customize.sh"))


if __name__ == "__main__":
    unittest.main()

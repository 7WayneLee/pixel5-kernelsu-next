"""Cached baselines cannot relax source or stock configuration checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from baseline import validate
from common import ROOT, artifact_file_names, digest, profile


def cached_artifact(root, extra_config=""):
    base = profile()
    for name in artifact_file_names(base):
        (root / name).write_bytes(b"fixture")
    for name in ("Module.symvers", "baseline.Module.symvers"):
        (root / name).write_text("0x00000001 fixture vmlinux\n")
    (root / "baseline.config").write_text((ROOT / base["config"]).read_text() + extra_config)
    (root / "source-lock.json").write_bytes((ROOT / base["source_lock"]).read_bytes())
    info = {"schema_version": 1, "profile": base, "kernel_release": base["kernel_release"],
            "abi_compatible": True, "files": {name: digest(root / name)
                                              for name in artifact_file_names(base)}}
    (root / "build-info.json").write_text(json.dumps(info))


class BaselineTests(unittest.TestCase):
    def test_different_kernel_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cached_artifact(root)
            target = profile("redfin-up1a-231105-001-b2-susfs")
            target["kernel_revision"] = "0" * 40
            with self.assertRaisesRegex(ValueError, "kernel_revision"):
                validate(root, target)

    def test_baseline_with_root_enabled_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cached_artifact(root, "\nCONFIG_KSU=y\n")
            with self.assertRaisesRegex(ValueError, "stock config"):
                validate(root, profile("redfin-up1a-231105-001-b2-susfs"))


if __name__ == "__main__":
    unittest.main()

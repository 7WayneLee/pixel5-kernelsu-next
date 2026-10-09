"""Reuse a checksum-verified stock baseline only for identical pinned sources."""
import json
from pathlib import Path

from common import ROOT, config_values, digest, profile
from pack_boot import check_artifact


def validate(directory: Path, target: dict) -> dict:
    base = profile()
    info = check_artifact(directory, base)
    for key in ("kernel_revision", "kernel_release", "config", "source_lock", "scmversion"):
        if target[key] != base[key]:
            raise ValueError(f"Cached stock baseline differs: {key}")
    if json.loads((directory / "source-lock.json").read_text()) != json.loads(
            (ROOT / target["source_lock"]).read_text()):
        raise ValueError("Cached baseline Google sources differ")
    actual = config_values(directory / "baseline.config")
    expected = config_values(ROOT / target["config"])
    # Google's build generates this same symbol list at the current OUT_DIR.
    ignored = {"CONFIG_UNUSED_KSYMS_WHITELIST"}
    drift = {key: [value, actual.get(key)] for key, value in expected.items()
             if key not in ignored and actual.get(key) != value}
    if drift or any(key.startswith("CONFIG_KSU") and value != "n"
                    for key, value in actual.items()):
        raise ValueError(f"Cached baseline is not the exact stock config: {drift}")
    return {"kind": "validated-artifact", "profile": base["id"],
            "kernel_revision": base["kernel_revision"],
            "files": {name: digest(directory / name) for name in
                      ("baseline.config", "baseline.Module.symvers", "source-lock.json", "build-info.json")}}

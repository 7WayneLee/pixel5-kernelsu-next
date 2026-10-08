"""Fetch only immutable Google source revisions into a new workspace."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from common import ROOT, PROFILE_ID, profile


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def checkout(project: dict, root: Path):
    relative = PurePosixPath(project["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe source path")
    if not project["url"].startswith("https://android.googlesource.com/"):
        raise ValueError("Unexpected source host")
    if not re.fullmatch(r"[0-9a-f]{40}", project["revision"]):
        raise ValueError("Source revision must be a full commit")
    target = root / relative
    target.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        raise ValueError(f"Source checkout already exists: {target}; use a new workspace")
    run("git", "init", "--quiet", str(target))
    run("git", "-C", str(target), "remote", "add", "origin", project["url"])
    run("git", "-C", str(target), "-c", "protocol.version=2", "fetch",
        "--depth=1", "origin", project["revision"])
    run("git", "-C", str(target), "checkout", "--quiet", "--detach", "FETCH_HEAD")
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if actual != project["revision"]:
        raise ValueError("Fetched source revision does not match lock")
    print(f"Pinned {project['path']} at {actual}", flush=True)


def sync(root: Path, p: dict, jobs: int):
    if root.exists() and any(root.iterdir()):
        raise ValueError("Source workspace must be empty")
    root.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / p["source_lock"]).read_text())
    pending = list(lock["projects"])
    # Parent repos must be checked out before repos nested in their trees.
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        while pending:
            ready = [item for item in pending if not any(
                item["path"].startswith(other["path"] + "/") for other in pending if item is not other)]
            list(pool.map(lambda item: checkout(item, root), ready))
            pending = [item for item in pending if item not in ready]
    for item in lock["projects"]:
        for link in item["linkfiles"]:
            dest = root / link["dest"]
            if dest.exists() or dest.is_symlink():
                raise ValueError(f"Link destination already exists: {dest}")
            dest.symlink_to(Path(item["path"]) / link["src"])
    (root / "source-lock.json").write_text(json.dumps(lock, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=PROFILE_ID)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    sync(args.workspace.resolve(), profile(args.profile), args.jobs)

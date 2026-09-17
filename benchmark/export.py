"""Export exact package artifacts and reject non-additive environment transitions."""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent
(ROOT / "results").mkdir(exist_ok=True)
subprocess.run([
    "pixi", "workspace", "export", "conda-explicit-spec", "--manifest-path",
    str(ROOT / "pixi.toml"), "--locked", "--ignore-pypi-errors",
    "--environment", "core", "--environment", "nwb", "--environment", "aind",
    str(ROOT / "specs"),
], check=True)
packages = {}
for environment in ("core", "nwb", "aind"):
    lines = (ROOT / f"specs/{environment}_linux-64_conda_spec.txt").read_text().splitlines()
    packages[environment] = set(line for line in lines if line.startswith("https:"))
summary = {}
for parent, child in (("core", "nwb"), ("nwb", "aind")):
    removed = packages[parent] - packages[child]
    if removed:
        raise RuntimeError(f"{parent} -> {child} replaces or removes packages: {removed}")
    delta = sorted(packages[child] - packages[parent])
    (ROOT / f"specs/{child}-delta.txt").write_text("@EXPLICIT\n" + "\n".join(delta) + "\n")
    summary[f"{parent}->{child}"] = {"unchanged": len(packages[parent]), "added": len(delta), "removed": 0}
lock = (ROOT / "pixi.lock").read_text()
match = re.search(r"^- pypi: (.+remfile[^\n]+)\n  name: remfile\n  version: [^\n]+\n  sha256: (\w+)", lock, re.M)
if match is None:
    raise RuntimeError("Expected exactly one PyPI fallback, remfile")
names = re.findall(r"^- pypi: (.+)", lock, re.M)
if len(names) != 1:
    raise RuntimeError(f"Unexpected PyPI artifacts: {names}")
(ROOT / "specs/remfile.txt").write_text(match[1] + " --hash=sha256:" + match[2] + "\n")
(ROOT / "results/package-deltas.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))

"""Measure cached builds and controlled source/dependency changes, restoring inputs."""

import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent

def build(variant, target, case):
    subprocess.run([sys.executable, str(ROOT / "build.py"), variant, target, "--case", case], check=True)

for repeat in (1, 2):
    for variant in ("baseline", "pixi"):
        for target in ("core-cache", "nwb-cache", "aind"):
            build(variant, target, f"warm{repeat}")

source = ROOT / "repos/dandi-cache-utils/src/dandi_cache_utils/__init__.py"
original = source.read_bytes()
try:
    source.write_bytes(original + b"\n# Benchmark source-only cache invalidation.\n")
    for variant in ("baseline", "pixi"):
        for target in ("core", "nwb", "core-cache", "nwb-cache", "aind"):
            build(variant, target, "source")
finally:
    source.write_bytes(original)

paths = [ROOT / "pixi.toml", ROOT / "pixi.lock", ROOT / "Dockerfile.baseline"]
paths += list((ROOT / "specs").iterdir())
paths += [ROOT / "results/package-deltas.json"]
originals = {path: path.read_bytes() for path in paths}
try:
    manifest = ROOT / "pixi.toml"
    manifest.write_text(manifest.read_text().replace("[feature.nwb.dependencies]", '[feature.nwb.dependencies]\nhumanfriendly = "*"'))
    started = time.perf_counter()
    with (ROOT / "results/lock-nwb-change.log").open("w") as log:
        subprocess.run(["pixi", "lock", "--manifest-path", str(manifest)], stdout=log, stderr=subprocess.STDOUT, check=True)
    (ROOT / "results/lock-nwb-change.json").write_text(json.dumps({"seconds": time.perf_counter() - started}))
    subprocess.run([sys.executable, str(ROOT / "export.py")], check=True)
    core_spec = ROOT / "specs/core_linux-64_conda_spec.txt"
    if core_spec.read_bytes() != originals[core_spec]:
        raise RuntimeError("NWB-only addition unexpectedly changed the core resolution")
    baseline = ROOT / "Dockerfile.baseline"
    baseline.write_text(baseline.read_text().replace('RUN pip install "${DANDI_CACHE_UTILS_DIR}[nwb]"', 'RUN pip install "${DANDI_CACHE_UTILS_DIR}[nwb]" humanfriendly'))
    for variant in ("baseline", "pixi"):
        for target in ("nwb-cache", "aind"):
            build(variant, target, "nwb-addition")
finally:
    for path, data in originals.items():
        path.write_bytes(data)

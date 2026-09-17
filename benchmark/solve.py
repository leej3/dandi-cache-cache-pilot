"""Compare lock generation with cold metadata and shared warm metadata."""

import json
import os
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent
manifest = (ROOT / "pixi.toml").read_text()
env = dict(os.environ, PIXI_CACHE_DIR=str(ROOT / "results/solve-cache"))
results = []
for case in ("group-cold", "group-warm1", "separate-warm1", "group-warm2", "separate-warm2"):
    targets = ("core", "nwb", "aind") if case.startswith("separate") else ("group",)
    total = 0.0
    for target in targets:
        directory = ROOT / "results/solve-cases" / f"{case}-{target}"
        directory.mkdir(parents=True, exist_ok=True)
        text = manifest
        if target != "group":
            prefix, environments = manifest.split("[environments]\n")
            line = next(line for line in environments.splitlines() if line.startswith(target + " ="))
            text = prefix + "[environments]\n" + line.replace(', solve-group = "runtime"', "") + "\n"
        path = directory / "pixi.toml"
        path.write_text(text)
        started = time.perf_counter()
        with (directory / "solve.log").open("w") as log:
            result = subprocess.run(["pixi", "lock", "--manifest-path", str(path)], env=env, stdout=log, stderr=subprocess.STDOUT)
        elapsed = time.perf_counter() - started
        results.append({"case": case, "environment": target, "seconds": elapsed, "returncode": result.returncode})
        total += elapsed
        if result.returncode:
            raise RuntimeError(f"{case}/{target} failed; see {directory}")
    print(case, round(total, 3), flush=True)
(ROOT / "results/solve-timings.json").write_text(json.dumps(results, indent=2))

"""Validate installed artifacts without changing measured image layers."""

import argparse
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
env = dict(os.environ)
env.setdefault("DOCKER_CONFIG", str(ROOT / "docker-config"))
desktop_socket = pathlib.Path.home() / ".docker/run/docker.sock"
if desktop_socket.exists():
    env.setdefault("DOCKER_HOST", f"unix://{desktop_socket}")
parser = argparse.ArgumentParser()
parser.add_argument("variant")
parser.add_argument("target")
parser.add_argument("--only", nargs="+")
parser.add_argument("--loaded", action="store_true")
args = parser.parse_args()
variant, target = args.variant, args.target
name = f"{variant}-{target}"
image = f"dandi-bench:{name}"
result_path = ROOT / "results" / f"{name}-validation.json"
results = json.loads(result_path.read_text()) if args.only and result_path.exists() else {}
if not args.loaded:
    with (ROOT / "results" / f"{name}-load.log").open("w") as log:
        subprocess.run([
            "docker", "buildx", "build", "--builder", "dandi-pixi-bench", "--platform", "linux/amd64",
            "--provenance=false", "--file", str(ROOT / f"Dockerfile.{variant}"),
            "--target", target, "--tag", image, "--load", str(ROOT),
        ], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
commands = {
    "metadata": "python -m pip list --format=json",
    "dependency-check": "python -m pip check",
    "disk": "du -sk /opt/*; git --version; git-annex version",
    "core-imports": "python /bench/repos/dandi-cache-utils/tests/check_core_imports.py",
    "pipeline": "bash -n /opt/dandi-cache-utils/src/dandi_cache_utils/pipeline/update_pipeline.sh",
    "functional": f"python /bench/smoke.py {target}",
    "suite": "pip install -q pytest bidsschematools && cd /bench/repos/dandi-cache-utils && python -m pytest tests -q -p no:cacheprovider",
}
repos = {"core": "dandiset-id-to-total-size", "nwb": "valid-nwb-file-to-number-of-groups", "aind": "qualifying-aind-content-ids"}
repo = repos[target]
commands["cache-script"] = f"cd /bench/repos/{repo} && dandi-cache check-operations && python code/update.py --help"
if variant in {"runtime", "baseline-runtime"}:
    commands["disk"] = "du -sk /opt/*"
for test, command in commands.items():
    if args.only and test not in args.only:
        continue
    result = subprocess.run([
        "docker", "run", "--rm", "--platform", "linux/amd64", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPYCACHEPREFIX=/tmp/pycache",
        "-v", f"{ROOT}:/bench:ro", image, "bash", "-c", command,
    ], env=env, capture_output=True, text=True)
    log_path = ROOT / "results" / f"{name}-{test}.log"
    if args.only and log_path.exists():
        log_path.rename(log_path.with_suffix(".previous.log"))
    log_path.write_text(result.stdout + result.stderr)
    results[test] = result.returncode
    print(name, test, result.returncode, flush=True)
result_path.write_text(json.dumps(results, indent=2))

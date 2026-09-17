"""Build one benchmark target and record real compressed OCI layer sizes."""

import argparse
import datetime
import json
import os
import pathlib
import subprocess
import tarfile
import time

ROOT = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("variant")
parser.add_argument("target")
parser.add_argument("--case", default="initial")
args = parser.parse_args()
name = f"{args.variant}-{args.target}-{args.case}"
output = ROOT / "results" / f"{name}.tar"
env = dict(os.environ)
env.setdefault("DOCKER_CONFIG", str(ROOT / "docker-config"))
desktop_socket = pathlib.Path.home() / ".docker/run/docker.sock"
if desktop_socket.exists():
    env.setdefault("DOCKER_HOST", f"unix://{desktop_socket}")
command = [
    "docker", "buildx", "build", "--builder", "dandi-pixi-bench",
    "--platform", "linux/amd64", "--progress", "plain", "--provenance=false",
    "--file", str(ROOT / f"Dockerfile.{args.variant}"), "--target", args.target,
    "--tag", f"dandi-bench:{args.variant}-{args.target}",
    "--output", f"type=oci,dest={output},compression=gzip,compression-level=6,force-compression=true",
    str(ROOT),
]
started = time.perf_counter()
with (ROOT / "results" / f"{name}.log").open("w") as log:
    result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
record = {
    "name": name, "variant": args.variant, "target": args.target, "case": args.case,
    "seconds": time.perf_counter() - started, "returncode": result.returncode,
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "command": command,
}
if result.returncode == 0:
    with tarfile.open(output) as archive:
        def read_blob(descriptor):
            path = "blobs/" + descriptor["digest"].replace(":", "/")
            return json.load(archive.extractfile(path))
        index = json.load(archive.extractfile("index.json"))
        manifest = read_blob(index["manifests"][0])
        while "manifests" in manifest:
            manifest = read_blob(manifest["manifests"][0])
        record["layers"] = manifest["layers"]
        record["compressed_bytes"] = sum(layer["size"] for layer in manifest["layers"])
        config = read_blob(manifest["config"])
        record["history"] = config.get("history", [])
        record["diff_ids"] = config["rootfs"]["diff_ids"]
with (ROOT / "results" / f"{name}.json").open("w") as stream:
    json.dump(record, stream, indent=2)
if result.returncode == 0 and args.case != "initial":
    output.unlink()
print(json.dumps({k: v for k, v in record.items() if k not in {"layers", "history", "diff_ids", "command"}}), flush=True)
raise SystemExit(result.returncode)

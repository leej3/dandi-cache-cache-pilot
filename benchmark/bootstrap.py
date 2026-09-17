"""Restore ignored local tooling using the recorded upstream checksum."""

import hashlib
import io
import json
import pathlib
import shutil
import ssl
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
tooling = ROOT / "tooling"
source = json.loads((tooling / "source.json").read_text())
with urllib.request.urlopen(source["url"], timeout=120) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != source["sha256"]:
    raise RuntimeError("The micromamba download does not match the recorded SHA-256")
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    executable = archive.extractfile("bin/micromamba")
    if executable is None:
        raise RuntimeError("The installer archive is missing bin/micromamba")
    destination = tooling / "micromamba"
    destination.write_bytes(executable.read())
    destination.chmod(0o755)

candidates = [ssl.get_default_verify_paths().cafile, "/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"]
bundle = next((pathlib.Path(path) for path in candidates if path and pathlib.Path(path).is_file()), None)
if bundle is None:
    raise RuntimeError("No system CA bundle found; supply benchmark/tooling/bootstrap-ca.pem")
shutil.copyfile(bundle, tooling / "bootstrap-ca.pem")
configuration = ROOT / "docker-config"
configuration.mkdir(exist_ok=True)
if not (configuration / "config.json").exists():
    (configuration / "config.json").write_text("{}\n")
print("Verified micromamba and restored local benchmark prerequisites.")

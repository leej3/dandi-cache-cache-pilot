# DANDI Cache cache pilot

An experimental comparison of DANDI Cache container builds using APT/pip and a shared Pixi lock with additive dependency layers.

Read the [benchmark results](benchmark/REPORT.md) and [reproduction guide](benchmark/README.md).
The pilot improves rebuild time and layer reuse, but conda-first packaging does not reduce total image size by itself.
The report documents dependency-check failures that must be resolved before production use.

## Get the pilot

```bash
git clone --recurse-submodules git@github.com:leej3/dandi-cache-cache-pilot.git
cd dandi-cache-cache-pilot
python3 benchmark/bootstrap.py
```

For an existing checkout, run `git submodule update --init --recursive`.
The four upstream repositories are pinned as submodules under `benchmark/repos/` at the commits used for the measurements.
Their HTTPS submodule URLs allow read-only cloning without SSH credentials.

The repository tracks benchmark scripts, Dockerfiles, manifests, locks, package specifications, reports and raw timing/validation evidence.
Large OCI archives, package caches, Docker configuration, the downloaded installer and the host certificate bundle remain local.
The bootstrap script restores the installer from its recorded URL after verifying its SHA-256 and copies a local CA bundle for verified build-time downloads.

## Documentation checks

Install Snapper and pre-commit, then run `pre-commit run --all-files`.
The local Snapper hook formats Markdown with semantic line breaks.

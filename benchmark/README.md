# DANDI Cache image pilot

This is a local benchmark, not a deployment or a proposed production migration.
No images were pushed and no upstream source repository was changed.
See [REPORT.md](REPORT.md) for measured results and limitations.

## Repositories

- `dandi-cache-utils`: shared core and NWB environments.
- `dandiset-id-to-total-size`: a cache with no additional core dependencies.
- `valid-nwb-file-to-number-of-groups`: a cache with no additional NWB dependencies.
- `qualifying-aind-content-ids`: NWB plus NumPy and SpikeInterface.

Exact source commits are recorded in `results/sources.json`.
The clones under `repos/` retain their original files.
The benchmark Dockerfiles live outside those clones.

## Variants

| Dockerfile | Dependency installation | Git and git-annex |
| --- | --- | --- |
| `Dockerfile.baseline` | Upstream APT and pip instructions | Included |
| `Dockerfile.pixi` | Shared Pixi lock, exact additive package installs | Included |
| `Dockerfile.baseline-runtime` | Upstream APT and pip instructions | Omitted |
| `Dockerfile.runtime` | Shared Pixi lock, exact additive package installs | Omitted |

The baseline changes only build-context paths and joins the existing parent/child Dockerfiles into named stages.
It preserves the upstream package installation commands and their order.
The runtime variants remove tools used by host-side orchestration, while keeping the processing dependencies.
They do not measure the runner environment.

Pixi resolves the core, NWB, and AIND features in one `runtime` solve group.
All shared conda packages retain exactly the same artifact URLs across environments.
`export.py` rejects removals or replacements and generates explicit addition lists.
The named environments are materialized into the same `/opt/env` prefix.
Micromamba is used only as the explicit-package installer, not as a solver.
Its executable is bind-mounted into build steps and is absent from the final image.
`remfile` is installed from the exact wheel URL and SHA-256 in `pixi.lock`, with dependency resolution disabled.
The local `dandi-cache-utils` package is installed with `--no-deps --no-build-isolation`.

The conda DANDI package currently has metadata/dependency problems described in the report.
These experimental images are not ready to replace production images as-is.

## Measurement

All images target `linux/amd64` on the same ARM Mac through Docker Desktop emulation.
Builds run sequentially through an isolated BuildKit builder.
Timing includes image export to a local OCI archive, with gzip level 6 forced for all layers.
Image loading into Docker and runtime tests are outside the build timer.
There are no registry pushes or pull-speed measurements.

`compressed_bytes` is the sum of actual OCI manifest layer sizes, not the uncompressed `docker images` size or the tar archive size.
Layers are compared by digest to measure potential registry upload/download reuse.
All numbers use decimal MB unless explicitly stated otherwise.

Initial builds have uncached dependency installation layers but reuse parent layers already built in the sweep.
They are not five independent cold builds.
The Pixi OS base was already fetched by a failed certificate-bootstrap attempt before its successful timed build.
Both variants use network downloads without a persistent package-download cache.
The first variant ran before the second, so network variability and emulation prevent extrapolating these timings directly to GitHub-hosted runners.

`cases.py` measures two fully cached runs, one source-only edit, and one NWB-only addition of `humanfriendly`.
It restores the original files after each scenario.
The NWB-only addition must leave the exported core specification byte-identical.
`solve.py` separately measures one metadata-cold grouped lock generation and two warm comparisons against three independent solves.
Solve times are not included in the Docker build timings.

## Reproduction

Requirements: Python 3, Pixi 0.76.2, Docker with Buildx and `linux/amd64` execution support.
After cloning with submodules, run `python3 benchmark/bootstrap.py` to restore the ignored local tooling.
The downloaded installer is micromamba 2.9.0; its upstream URL and SHA-256 are in `tooling/source.json`.
`tooling/bootstrap-ca.pem` bootstraps verified TLS before conda CA certificates are installed.
It was copied from the host's `/etc/ssl/cert.pem`.

The local Docker configuration in `docker-config/` contains no credentials.
It bypasses a hanging host credential helper for these public downloads.
Set `DOCKER_HOST` if the daemon is not at its normal location.
On this Mac the scripts detect the Docker Desktop socket automatically.

```bash
export DOCKER_CONFIG="$PWD/benchmark/docker-config"
docker buildx create --name dandi-pixi-bench --driver docker-container --bootstrap
python3 benchmark/export.py
python3 benchmark/export.py benchmark/runtime

python3 benchmark/build.py baseline core
python3 benchmark/build.py baseline nwb
python3 benchmark/build.py baseline core-cache
python3 benchmark/build.py baseline nwb-cache
python3 benchmark/build.py baseline aind

python3 benchmark/build.py pixi core
python3 benchmark/build.py pixi nwb
python3 benchmark/build.py pixi core-cache
python3 benchmark/build.py pixi nwb-cache
python3 benchmark/build.py pixi aind

python3 benchmark/cases.py
python3 benchmark/solve.py
python3 benchmark/validate.py pixi nwb
python3 benchmark/validate.py pixi aind
```

Run timing comparisons without concurrent builds or tests.
For another truly metadata-cold solve run, choose an empty `PIXI_CACHE_DIR` and fresh solve-case directories in `solve.py`.
For a fresh dependency-layer build, use a new isolated builder rather than deleting unrelated Docker caches.
The Dockerfiles use moving base tags; original resolved image digests are retained in the build logs for exact base-image reproduction.

## Validation

The existing 121-test shared-library suite runs against the installed distribution in each tested image.
`smoke.py` runs the core cache with small synthetic input files and verifies its output.
It also writes and reads real NWB/HDF5 and Zarr fixtures and reads NWB traces through SpikeInterface for AIND.
Cache entry-point imports, CLI checks, the pipeline shell syntax, and the core-import contract are checked separately.
No full DataLad update is dispatched and no production data is published.

An initial harness error made `compileall` try to write into a read-only source mount.
The harness was corrected to set `PYTHONPYCACHEPREFIX=/tmp/pycache` and the affected suites were rerun.
The earlier failure logs are retained as `*.previous.log`.

The current production CI also explicitly invokes `/usr/bin/python3` inside images.
The Pixi prototype supplies Python at `/opt/env/bin/python`, so those checks need adaptation before rollout.

## Files

- `pixi.toml`, `pixi.lock`: full runtime resolution with Git tools.
- `runtime/pixi.toml`, `runtime/pixi.lock`: processing-only resolution.
- `specs/`, `runtime/specs/`: exact package artifacts and additive transitions.
- `build.py`, `cases.py`, `solve.py`, `validate.py`, `smoke.py`: benchmark and verification scripts.
- `results/*.json`: measurements, OCI layer descriptors, source revisions, and test statuses.
- `results/*.log`: raw command output.
- `results/*-initial.tar`: local, untracked OCI image archives; subsequent scenario archives are deleted after their metadata is recorded.

The benchmark-specific images, builder, and its cache remain available locally for follow-up work.

# DANDI Cache cache pilot

## Decision: do not roll out organization-wide on this evidence

**The pilot has not demonstrated faster scheduled updates or smaller complete images with Git and git-annex retained.** The measured image-build improvements do not currently justify the additional machinery for an organization-wide switch.

- **Fresh GitHub-hosted runners still need the image bytes.** Each scheduled update starts without the previous job's local Docker layers.
  Restoring a saved image from Actions cache downloads and loads those bytes instead of pulling them from GHCR.
  It might be faster, but we have not measured either approach on those runners.
  The roughly 0.15 MB of changed layers is not the total download for a fresh runner.
- **The demonstrated speedup is in image builds.** The local core build fell from 92 to 37 seconds and a source-only core rebuild from 51 to 4 seconds.
  Fully cached builds were about 2.6–2.7 seconds with either approach.
  The existing workflows already use BuildKit caching; that does not automatically restore Docker images for separate scheduled update jobs.
- **Equivalent-scope images became larger.** With Git/git-annex retained, core/NWB/AIND increased from 364/390/395 MB to 401/402/409 MB compressed.
  Smaller experimental variants omitted those tools, but their removal was not validated through the complete pipeline and is not an established migration benefit.
- **The prototype adds maintenance work.** It uses a shared Pixi solve group, per-environment lock exports, micromamba for exact artifact installation, additive-package checks, a PyPI fallback, and revised Docker stages.
  Conda DANDI packaging issues still fail dependency checks, and existing CI interpreter-path checks need changes.
- **The timings have limits.** They were measured locally under amd64 emulation on an ARM Mac, with some dependency-version differences.
  No production CI startup, cached image restoration, registry transfer, or complete real-data pipeline speedup was measured.
  An optimized locked uv/pip control was not tested, so the build gains cannot all be attributed to Pixi.

Keep the current organization-wide approach for now.
Consider simpler dependency consistency and Docker-layer improvements within the existing tooling first.
Revisit a migration only if another repository has materially different dependency or build costs, or measurements on fresh GitHub runners demonstrate enough end-to-end benefit to justify it.
This pilot sampled the shared base and three caches; it is not an exhaustive dependency audit of the organization.

Read the [benchmark results](benchmark/REPORT.md) and [reproduction guide](benchmark/README.md).
GitHub documents the [fresh-runner model](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), and Docker documents the separate [BuildKit cache mechanism](https://docs.docker.com/build/ci/github-actions/cache/).

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

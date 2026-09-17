"""Render the measured comparison from retained JSON records."""

import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "results"

def record(variant, target, case="initial"):
    return json.loads((RESULTS / f"{variant}-{target}-{case}.json").read_text())

def new_bytes(before, after):
    previous = {layer["digest"] for layer in before["layers"]}
    return sum(layer["size"] for layer in after["layers"] if layer["digest"] not in previous)

size_rows = []
for name, target in [
    ("Core / dandiset-id-to-total-size", "core"),
    ("NWB / valid-nwb-file-to-number-of-groups", "nwb"),
    ("qualifying-aind-content-ids", "aind"),
]:
    sizes = [record(variant, target)["compressed_bytes"] / 1e6 for variant in ("baseline", "pixi", "baseline-runtime", "runtime")]
    size_rows.append("| " + name + " | " + " | ".join(f"{size:.1f}" for size in sizes) + " |")

time_rows = []
for case, target, label in [
    ("initial", "core", "Initial core build"),
    ("initial", "nwb", "Initial NWB extension, parent available"),
    ("initial", "aind", "Initial AIND extension, parent available"),
    ("source", "core", "Source-only core rebuild"),
    ("source", "nwb", "Source-only NWB rebuild, preceding core build complete"),
    ("source", "aind", "Source-only AIND rebuild, preceding NWB build complete"),
    ("nwb-addition", "nwb-cache", "NWB-only dependency addition"),
]:
    baseline = record("baseline", target, case)["seconds"]
    pixi = record("pixi", target, case)["seconds"]
    time_rows.append(f"| {label} | {baseline:.1f} | {pixi:.1f} | {baseline / pixi:.1f}× |")

layer_rows = []
for target in ("core", "nwb", "aind"):
    values = [new_bytes(record(v, target), record(v, target, "source")) / 1e6 for v in ("baseline", "pixi")]
    layer_rows.append(f"| Source-only {target} edit | {values[0]:.3f} | {values[1]:.3f} |")
for parent, child in (("core", "nwb"), ("nwb", "aind")):
    values = [new_bytes(record(v, parent), record(v, child)) / 1e6 for v in ("baseline", "pixi")]
    layer_rows.append(f"| {parent} → {child} image extension | {values[0]:.3f} | {values[1]:.3f} |")
values = [new_bytes(record(v, "nwb-cache"), record(v, "nwb-cache", "nwb-addition")) / 1e6 for v in ("baseline", "pixi")]
layer_rows.append(f"| NWB dependency addition | {values[0]:.3f} | {values[1]:.3f} |")

warm = {}
for variant in ("baseline", "pixi"):
    warm[variant] = statistics.median(json.loads(path.read_text())["seconds"] for path in RESULTS.glob(f"{variant}-*-warm*.json"))
solves = json.loads((RESULTS / "solve-timings.json").read_text())
solve_totals = {}
for item in solves:
    solve_totals[item["case"]] = solve_totals.get(item["case"], 0) + item["seconds"]
metadata = {}
for variant in ("baseline", "pixi"):
    metadata[variant] = {item["name"].lower().replace("_", "-"): item["version"] for item in json.loads((RESULTS / f"{variant}-aind-metadata.log").read_text())}
version_rows = [f"| {name} | {metadata['baseline'].get(name, 'absent')} | {metadata['pixi'].get(name, 'absent')} |" for name in ("dandi", "boto3", "botocore", "pynwb", "h5py", "hdmf-zarr", "zarr", "spikeinterface", "numpy", "etelemetry", "bids-validator-deno")]
validation_rows = []
for variant in ("baseline", "pixi", "baseline-runtime", "runtime"):
    for target in ("core", "nwb", "aind"):
        checks = json.loads((RESULTS / f"{variant}-{target}-validation.json").read_text())
        assert all(value == 0 for key, value in checks.items() if key != "dependency-check"), (variant, target, checks)
        validation_rows.append(f"| {variant}/{target} | 121 passed | Passed | {'Passed' if checks['dependency-check'] == 0 else 'Failed; see below'} |")

text = f"""# DANDI Cache Pixi pilot results

Measured September 17, 2026 across the shared `dandi-cache-utils` repository and three cache repositories.
**Decision: do not roll out organization-wide on this evidence.**
The added maintenance machinery is not justified by a demonstrated improvement in scheduled updates on fresh GitHub-hosted runners.
See the [decision summary](../README.md#decision-do-not-roll-out-organization-wide-on-this-evidence).

The additive lock/layer design substantially improves rebuilds and the amount of changed image data.
Moving almost everything to conda-forge does not make the complete images smaller in this pilot.
Experimentally omitting Git/git-annex makes either packaging approach smaller, but the complete pipeline was not tested without them.

Each fresh runner must obtain the image bytes from GHCR or a restored cache.
Smaller changed layers do not imply a 0.15 MB full-image download for a fresh runner.
Restoring and loading a cached image might be faster than a registry pull, but neither that comparison nor scheduled-update startup was measured.
BuildKit caching helps image builds; it does not automatically populate the Docker image cache of a separate update job.

## Compressed image sizes

Actual gzip-compressed OCI layer bytes, decimal MB.
The small empty cache-environment distribution adds about 0.002 MB in the baseline cache wrappers; rounded values below also describe those cache images.

| Image / cache | Current APT + pip | Pixi, same tools | APT + pip, runtime only | Pixi, runtime only |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(size_rows)}

With the same tool scope, Pixi increases the full image size by about 10.4% for core, 3.0% for NWB, and 3.4% for AIND.
The processing-only Pixi images are 19–25% smaller than the original images, but the similarly trimmed APT/pip images are smaller still.
Those savings come from omitting Git, git-annex and their dependencies, not from the package manager.
That omission is an experimental change in capabilities, not a validated equivalent replacement.

## Build timing

Seconds, including local gzip OCI export, excluding image loading and tests.
These are local `linux/amd64` builds under emulation on an ARM Mac, not GitHub-hosted runner measurements.
Initial and changed builds are single observations; warm builds were repeated twice for each of the three cache targets.

| Scenario | APT + pip | Pixi lock + additive installation | Observed speedup |
| --- | ---: | ---: | ---: |
{chr(10).join(time_rows)}

Fully cached median build/export time was {warm['baseline']:.2f} seconds for APT/pip and {warm['pixi']:.2f} seconds for Pixi.
There is no meaningful warm-cache improvement.

The sequential sweep producing core, NWB and all three cache targets took 126.5 seconds for the baseline and 56.3 seconds for Pixi.
The source-only sweep took 86.7 versus 16.9 seconds.
These totals include multiple exports and reuse parents built earlier in the same sweep.
They are not independent cold-build times for every image.

The runtime-only core build took 79.1 seconds with APT/pip and 28.2 seconds with Pixi.
The controlled NWB dependency addition required an additional 1.56-second lock update outside the Pixi Docker timer.

## Changed layers and the final-image extension

This table counts compressed layer digests absent from the previous image.
It estimates potentially new registry bytes; no registry transfer was performed.

| Change | APT + pip new MB | Pixi new MB |
| --- | ---: | ---: |
{chr(10).join(layer_rows)}

The Pixi NWB environment adds three conda packages plus the locked `remfile` wheel, preserving all 199 core conda artifacts.
AIND adds five conda packages and replaces none of the 202 NWB artifacts.
The runtime-only variant has four fewer core packages.
The actual micromamba logs show only `Linking` operations for those additions, with no unlinks or downgrades.

Net full-image growth from core to NWB is 26.674 MB in the baseline and 0.449 MB in Pixi.
The new-layer figure is slightly larger for Pixi because each final image separately installs the small application package after the shared dependency stages.
The AIND extension is larger under conda packaging, so small additive changes do not guarantee a smaller extension for every package.

For the NWB-only `humanfriendly` addition, the core package export remained byte-identical and its Docker layer was reused.
Only the NWB and downstream AIND environment layers needed rebuilding.
Copying the entire shared lock into the core stage would have lost that property; the per-environment exports are important.

## Solver measurements

All three environments share one Pixi solve group.
With a fresh metadata cache, combined lock generation took {solve_totals['group-cold']:.2f} seconds.
With warm metadata it took {solve_totals['group-warm1']:.2f} and {solve_totals['group-warm2']:.2f} seconds.
Three independent solves with warm metadata took {solve_totals['separate-warm1']:.2f} and {solve_totals['separate-warm2']:.2f} seconds in total.

The independent solves are allowed to choose different shared-package versions; the grouped solve guarantees compatibility.
This is a comparison of lock-generation approaches within Pixi, not a claim that Pixi's solver is a particular factor faster than APT or pip.
The original build logs do not separately time pip solving, downloading and installation.
Most of the large rebuild improvement comes from locked installation and keeping dependency layers independent of application source.
A similarly organized locked uv/pip baseline was not benchmarked, so the speedup cannot all be attributed to conda or Pixi itself.

## Functional checks and packaging findings

| Variant / environment | Existing shared suite | Local processing fixture | `pip check` |
| --- | --- | --- | --- |
{chr(10).join(validation_rows)}

The fixtures exercise the real core cache with synthetic inputs, NWB/HDF5 and Zarr writing and reading, and SpikeInterface reading NWB traces.
Core-import checks, cache CLI/operation checks, and shell syntax also pass.
They do not exercise a full remote-data DataLad update or the DANDI BIDS-validator path.

The current pip NWB/AIND build downgrades `botocore` from 1.43.97 to 1.43.75 while leaving `boto3` at 1.43.97.
`pip check` correctly reports the incompatible dependency.
The joint Pixi solve selects `boto3` and `botocore` 1.43.75 together.

The conda DANDI distribution has two separate problems:

1. Its Python metadata requires `bids-validator-deno`, but the installed conda dependency graph does not provide that distribution.
2. The conda `etelemetry` package is selected as version 0.3.1, but its installed Python metadata reports `0+unknown`, failing DANDI's version requirement.

The experimental Pixi images should not be rolled out unchanged.
Correct these recipes or make the affected distributions explicit PyPI exceptions and rerun the compatibility checks.
The CI checks that use `/usr/bin/python3` also need adaptation to the Pixi interpreter path.

## Version differences

The existing dependency declarations mostly allow any version, so each package ecosystem resolves its available versions.
This is a practical migration comparison, not an identical-version packaging benchmark.

| Package | APT/pip AIND | Pixi AIND |
| --- | --- | --- |
{chr(10).join(version_rows)}

In particular, conda-forge's DANDI and SpikeInterface releases lagged the PyPI selections in this run.
These differences and the missing validator affect the interpretation of image size.

## Recommendation

Keep the current organization-wide tooling for now.
The pilot preserves shared package builds, prevents the observed boto3/botocore conflict, and keeps source-only updates tiny.
Those benefits do not establish a worthwhile improvement for scheduled updates on fresh GitHub-hosted runners.
The prototype also introduces shared locks, environment exports, a separate installer, additive-package checks and packaging exceptions.

Retain Git/git-annex unless a complete pipeline validation establishes that removing them preserves the supported behavior.
Prioritize simpler dependency consistency and Docker-layer improvements within the existing tooling.
Do not treat experimental tool removal as evidence that a Pixi migration reduces equivalent-scope image size.

Revisit migration if a repository has materially different dependency or build costs, or native GitHub-runner measurements show worthwhile end-to-end savings.
This pilot sampled four repositories and did not audit every repository in the organization.
A further comparison should include an optimized locked uv/pip control and GHCR pull versus Actions-cache restore plus `docker load` on fresh runners.
Include dependency installation, cache restoration, image loading and a bounded real-data update in the elapsed time.
The existing local ratios are not forecasts of production CI performance.

No production images or upstream source repositories were changed.
See [README.md](README.md) for implementation, reproduction commands and measurement details.
Raw logs, exact source SHAs, dependency locks and OCI manifests are retained under this benchmark directory.
"""
(ROOT / "REPORT.md").write_text(text)
print(ROOT / "REPORT.md")

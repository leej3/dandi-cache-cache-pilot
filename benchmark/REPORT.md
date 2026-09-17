# DANDI Cache Pixi pilot results

Measured September 17, 2026 across the shared `dandi-cache-utils` repository and three cache repositories.
**Decision: do not roll out organization-wide on this evidence.** The added maintenance machinery is not justified by a demonstrated improvement in scheduled updates on fresh GitHub-hosted runners.
See the [decision summary](../README.md#decision-do-not-roll-out-organization-wide-on-this-evidence).

The additive lock/layer design substantially improves rebuilds and the amount of changed image data. Moving almost everything to conda-forge does not make the complete images smaller in this pilot. Experimentally omitting Git/git-annex makes either packaging approach smaller, but the complete pipeline was not tested without them.

Each fresh runner must obtain the image bytes from GHCR or a restored cache.
Smaller changed layers do not imply a 0.15 MB full-image download for a fresh runner.
Restoring and loading a cached image might be faster than a registry pull, but neither that comparison nor scheduled-update startup was measured.
BuildKit caching helps image builds; it does not automatically populate the Docker image cache of a separate update job.

## Compressed image sizes

Actual gzip-compressed OCI layer bytes, decimal MB.
The small empty cache-environment distribution adds about 0.002 MB in the baseline cache wrappers; rounded values below also describe those cache images.

| Image / cache | Current APT + pip | Pixi, same tools | APT + pip, runtime only | Pixi, runtime only |
| --- | ---: | ---: | ---: | ---: |
| Core / dandiset-id-to-total-size | 363.5 | 401.4 | 257.0 | 293.1 |
| NWB / valid-nwb-file-to-number-of-groups | 390.2 | 401.8 | 283.7 | 293.5 |
| qualifying-aind-content-ids | 395.1 | 408.6 | 288.7 | 300.3 |

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
| Initial core build | 91.8 | 37.3 | 2.5× |
| Initial NWB extension, parent available | 15.1 | 6.5 | 2.3× |
| Initial AIND extension, parent available | 8.0 | 6.2 | 1.3× |
| Source-only core rebuild | 50.8 | 4.0 | 12.7× |
| Source-only NWB rebuild, preceding core build complete | 15.9 | 3.8 | 4.2× |
| Source-only AIND rebuild, preceding NWB build complete | 8.5 | 3.8 | 2.3× |
| NWB-only dependency addition | 17.9 | 5.9 | 3.1× |

Fully cached median build/export time was 2.63 seconds for APT/pip and 2.73 seconds for Pixi.
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
| Source-only core edit | 167.974 | 0.165 |
| Source-only nwb edit | 194.648 | 0.142 |
| Source-only aind edit | 199.594 | 0.142 |
| core → nwb image extension | 26.674 | 0.616 |
| nwb → aind image extension | 4.946 | 6.951 |
| NWB dependency addition | 26.860 | 0.807 |

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
With a fresh metadata cache, combined lock generation took 3.61 seconds.
With warm metadata it took 1.13 and 1.10 seconds.
Three independent solves with warm metadata took 3.08 and 2.84 seconds in total.

The independent solves are allowed to choose different shared-package versions; the grouped solve guarantees compatibility.
This is a comparison of lock-generation approaches within Pixi, not a claim that Pixi's solver is a particular factor faster than APT or pip.
The original build logs do not separately time pip solving, downloading and installation.
Most of the large rebuild improvement comes from locked installation and keeping dependency layers independent of application source.
A similarly organized locked uv/pip baseline was not benchmarked, so the speedup cannot all be attributed to conda or Pixi itself.

## Functional checks and packaging findings

| Variant / environment | Existing shared suite | Local processing fixture | `pip check` |
| --- | --- | --- | --- |
| baseline/core | 121 passed | Passed | Passed |
| baseline/nwb | 121 passed | Passed | Failed; see below |
| baseline/aind | 121 passed | Passed | Failed; see below |
| pixi/core | 121 passed | Passed | Failed; see below |
| pixi/nwb | 121 passed | Passed | Failed; see below |
| pixi/aind | 121 passed | Passed | Failed; see below |
| baseline-runtime/core | 121 passed | Passed | Passed |
| baseline-runtime/nwb | 121 passed | Passed | Failed; see below |
| baseline-runtime/aind | 121 passed | Passed | Failed; see below |
| runtime/core | 121 passed | Passed | Failed; see below |
| runtime/nwb | 121 passed | Passed | Failed; see below |
| runtime/aind | 121 passed | Passed | Failed; see below |

The fixtures exercise the real core cache with synthetic inputs, NWB/HDF5 and Zarr writing and reading, and SpikeInterface reading NWB traces. Core-import checks, cache CLI/operation checks, and shell syntax also pass.
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
| dandi | 0.80.0 | 0.78.0 |
| boto3 | 1.43.97 | 1.43.75 |
| botocore | 1.43.75 | 1.43.75 |
| pynwb | 4.2.0 | 4.2.0 |
| h5py | 3.16.0 | 3.16.0 |
| hdmf-zarr | 0.13.0 | 0.13.0 |
| zarr | 2.18.7 | 2.18.7 |
| spikeinterface | 0.104.9 | 0.104.8 |
| numpy | 2.5.3 | 2.5.3 |
| etelemetry | 0.3.1 | 0+unknown |
| bids-validator-deno | 3.0.1 | absent |

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

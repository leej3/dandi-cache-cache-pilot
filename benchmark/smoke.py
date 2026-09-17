"""Exercise real processing with small local fixtures and no external writes."""

import datetime
import gzip
import json
import pathlib
import subprocess
import sys
import tempfile

import dandi_cache_utils

target = sys.argv[1]
with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory)
    if target == "core":
        repo = pathlib.Path("/bench/repos/dandiset-id-to-total-size")
        config = dandi_cache_utils.read_config(repo / "cache.toml")
        records = {
            "content-id-to-usage-dandiset-path": [{"a": {"000001": "a.nwb"}}, {"b": {"000001": "b.nwb"}}],
            "usage-dandiset-path-to-asset-size": [{"a": 10}, {"b": 20}],
        }
        for item in config.inputs:
            path = root / item.relative_file_path
            path.parent.mkdir(parents=True, exist_ok=True)
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "wt") as stream:
                stream.writelines(json.dumps(row) + "\n" for row in records[item.name])
        subprocess.run([sys.executable, "code/update.py", "--base-directory", str(root), "--testing"], cwd=repo, check=True)
        outputs = list((root / "derivatives").glob("testing_*.jsonl"))
        assert len(outputs) == 1, outputs
        assert json.loads(outputs[0].read_text()) == {"000001": 30}
    else:
        import h5py
        import hdmf_zarr
        import numpy
        import pynwb
        import pynwb.ecephys
        import remfile
        import s3fs
        import zarr

        nwb = pynwb.NWBFile("benchmark", "benchmark", datetime.datetime.now(datetime.timezone.utc))
        device = nwb.create_device("device")
        group = nwb.create_electrode_group("group", "test electrodes", "brain", device)
        for index in range(2):
            nwb.add_electrode(id=index, x=float(index), y=0.0, z=0.0, imp=0.0, location="brain", filtering="none", group=group)
        region = nwb.create_electrode_table_region([0, 1], "channels")
        series = pynwb.ecephys.ElectricalSeries(name="ElectricalSeries", data=numpy.zeros((2000, 2)), electrodes=region, rate=20000.0)
        nwb.add_acquisition(series)
        path = root / "fixture.nwb"
        with pynwb.NWBHDF5IO(str(path), "w") as stream:
            stream.write(nwb)
        with pynwb.NWBHDF5IO(str(path), "r") as stream:
            assert stream.read().acquisition["ElectricalSeries"].data.shape == (2000, 2)
        zarr.open_group(str(root / "fixture.zarr"), mode="w").create_dataset("data", data=numpy.arange(10))
        assert zarr.open_group(str(root / "fixture.zarr"))["data"][:].sum() == 45
        if target == "aind":
            import spikeinterface.extractors

            recording = spikeinterface.extractors.NwbRecordingExtractor(file_path=path, electrical_series_path="acquisition/ElectricalSeries")
            assert recording.get_num_channels() == 2
            assert recording.get_sampling_frequency() == 20000.0
            assert recording.get_traces(start_frame=0, end_frame=10).shape == (10, 2)
print(f"{target}: functional fixture passed")

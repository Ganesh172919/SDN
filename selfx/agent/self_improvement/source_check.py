"""Verify original replay bytes and rebuild curated splits without absolute paths."""
from pathlib import Path
from tempfile import TemporaryDirectory

import config
from .common import read,sha256
from .dataset import build_dataset


def verify_sources(dataset,source_map=None):
    dataset=Path(dataset)
    manifest=read(dataset/"manifest.json")
    map_path=Path(source_map) if source_map else dataset.parent.parent/"source_map.json"
    mapping=read(map_path)["sources"] if map_path.is_file() else {}
    sources=[]
    for original,checksum in manifest["source_sha256"].items():
        if original in mapping:
            path=(map_path.parent/mapping[original]).resolve()
            if not path.is_relative_to(map_path.parent.resolve()):
                raise ValueError("portable source map escapes its evidence folder")
        else:
            path=Path(original)
        if not path.is_file() or sha256(path)!=checksum:
            raise ValueError("original replay source is missing or altered")
        sources.append(path)
    temporary_root=config.PROJECT_ROOT/"tmp"
    temporary_root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="rebuild-replay-",dir=temporary_root) as directory:
        target=Path(directory).resolve()
        if not target.is_relative_to(temporary_root.resolve()):
            raise ValueError("temporary rebuild escaped workspace")
        rebuilt=build_dataset(sources,target,manifest["split_seeds"],manifest["min_reward"])
        for split in ("train","stress","holdout"):
            if rebuilt["splits"][split]!=manifest["splits"][split]:
                raise ValueError("curated dataset cannot be reproduced from original replay")
        if rebuilt["excluded"]!=manifest["excluded"]:
            raise ValueError("excluded cases cannot be reproduced from source")
    return {"status":"passed","source_files":len(sources),"splits_rebuilt":3,"excluded_audit_rebuilt":True}

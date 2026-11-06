"""Verify the extracted submission without importing project or ML packages."""
from pathlib import Path,PurePosixPath
import argparse
import hashlib


def verify_manifest(root,name):
    root=Path(root).resolve();manifest=root/name
    if not manifest.is_file():
        raise ValueError(f"missing checksum manifest: {name}")
    seen=set();count=0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        checksum,relative=line.split("  ",1)
        pure=PurePosixPath(relative)
        if (len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum)
            or pure.is_absolute() or '..' in pure.parts or '\\' in relative or ':' in relative
            or relative.casefold() in seen):
            raise ValueError("invalid or duplicate checksum entry")
        seen.add(relative.casefold())
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or unsafe submission file: {relative}")
        digest=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=checksum:
            raise ValueError(f"checksum mismatch: {relative}")
        count+=1
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default=str(Path(__file__).resolve().parents[1]))
    args=parser.parse_args();root=Path(args.root)
    counts={"submission_files":verify_manifest(root,"MANIFEST.sha256")}
    if (root/"MODEL_FILES.sha256").exists():
        counts["offline_model_files"]=verify_manifest(root,"MODEL_FILES.sha256")
    print({"status":"passed",**counts})


if __name__=="__main__":main()

"""Extract the fixed, approved CI artifact without building or editing its files."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

EXPECTED_ZIP = "259a17b10e088a0652f8e9a2684ac632caf06f51c2cc9006c9395bacc972e04e"
EXPECTED_MANIFEST = "607be48ed246b96ae93b5c887d2488e08392b36f599ee2e7463e9181b27ec82b"
EXPECTED_HEAD = "f0ea87bdba72569cd2e0ba8f0ebf05e2d6cdb5c3"
EXPECTED_MARKET = "bd5c0630bc3424e7c20aed05cf1f8801af90e34bd27563a9743615b907b1d7f9"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    archive = Path("approved-pr3-candidate.zip")
    require(digest(archive.read_bytes()) == EXPECTED_ZIP, "STOP: ZIP SHA256 mismatch")
    output = Path("site")
    require(not output.exists(), "STOP: extraction directory already exists")
    rows = []
    with zipfile.ZipFile(archive) as bundle:
        require(bundle.testzip() is None, "STOP: corrupt ZIP")
        manifest_bytes = bundle.read("release-manifest.json")
        require(digest(manifest_bytes) == EXPECTED_MANIFEST, "STOP: manifest SHA256 mismatch")
        manifest = json.loads(manifest_bytes)
        require(manifest["candidateCommit"] == EXPECTED_HEAD, "STOP: wrong candidate HEAD")
        require(manifest["asOf"] == "2026-10-13", "STOP: wrong observation date")
        require(manifest["profile"] == "observation-only", "STOP: wrong profile")
        require(manifest["localTreeDirty"] is False, "STOP: dirty candidate source")
        require(manifest["publishedDataSha256"] == EXPECTED_MARKET, "STOP: wrong market digest")
        names = bundle.namelist()
        require(len(names) == len(set(names)), "STOP: duplicate ZIP paths")
        require(set(names) == set(manifest["assets"]) | {"release-manifest.json"}, "STOP: file inventory mismatch")
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in item.filename, "STOP: unsafe ZIP path")
            require(not stat.S_ISLNK(item.external_attr >> 16), "STOP: symlink in ZIP")
            data = bundle.read(item.filename)
            expected = EXPECTED_MANIFEST if item.filename == "release-manifest.json" else manifest["assets"][item.filename]
            require(digest(data) == expected, "STOP: asset SHA256 mismatch: " + item.filename)
            target = output / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append({"path": item.filename, "bytes": len(data), "sha256": expected})
    report = {"candidateCommit": EXPECTED_HEAD, "sourceRun": 39748385578, "sourceArtifact": 12413090978, "zipSha256": EXPECTED_ZIP, "manifestSha256": EXPECTED_MANIFEST, "asOf": "2026-10-13", "rebuildPerformed": False, "files": rows}
    Path("candidate-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("PASS: original approved artifact extracted; all 8 files byte-verified; no build performed.")


if __name__ == "__main__":
    main()

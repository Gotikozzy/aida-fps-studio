"""Inventory an extracted candidate; verify reviewed native bytes before emitting a BOM."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def generate(payload: Path, policy: Path, installer: Path) -> dict:
    installer_hash = digest(installer)
    if installer_hash != "330f08d0daf617804ea145d0d0594a19d19b16868f6dd6bc54c826d9319585b0":
        raise ValueError("This generator inventories the verified unsigned 0.8.15 candidate only")
    review = json.loads((payload / "third_party_licenses/distribution-review.json").read_text("utf-8"))
    approval = json.loads(policy.read_text("utf-8"))
    if review["blockers"] or not review["public_release_allowed"]:
        raise ValueError("Native technical review has blockers")
    approved = {entry["sha256"]: entry for entry in approval["approved_binaries"]}
    native = {entry["path"]: entry for entry in review["native_files"]}
    for name, entry in native.items():
        path = (payload / name).resolve()
        if not path.is_relative_to(payload.resolve()):
            raise ValueError("Native review path escapes payload")
        if digest(path) != entry["sha256"] or entry["sha256"] not in approved:
            raise ValueError(f"Unreviewed native bytes: {name}")
        for notice, expected in approved[entry["sha256"]]["notice_sha256"].items():
            notice_path = (payload / notice).resolve()
            if not notice_path.is_relative_to(payload.resolve()) or digest(notice_path) != expected:
                raise ValueError(f"Notice mismatch: {notice}")
    components = []
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(payload).as_posix()
        component = {"type": "file", "name": name, "bom-ref": f"file:{name}",
                     "hashes": [{"alg": "SHA-256", "content": digest(path)}]}
        if name in native:
            entry = approved[native[name]["sha256"]]
            component["licenses"] = [{"license": {"name": entry["license"]}}]
            component["description"] = entry["component"]
        components.append(component)
    inventory = json.loads((payload / "third_party_licenses/inventory.json").read_text("utf-8"))
    for item in inventory:
        component = {"type": "library", "name": item["package"], "version": item["version"],
                     "bom-ref": f"package:{item['package']}@{item['version']}"}
        if item.get("license"):
            component["licenses"] = [{"license": {"name": item["license"]}}]
        components.append(component)
    components.append({"type": "file", "name": installer.name, "bom-ref": "file:outer-installer",
                       "hashes": [{"alg": "SHA-256", "content": installer_hash}]})
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "serialNumber": "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, installer_hash)),
            "metadata": {"component": {"type": "application", "name": "AIDA FPS Studio",
                                        "version": "0.8.15", "bom-ref": "aida-fps-studio:0.8.15"},
                         "properties": [{"name": "aida:scope", "value":
                             "Extracted NSIS archive including conditional files and installer helpers; "
                             "package metadata and file hashes, not a complete dependency graph or legal approval"},
                             {"name": "aida:native-review-count", "value": str(len(native))}]},
            "components": components}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("installer", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = generate(args.payload, args.policy, args.installer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(result['components'])} components")


if __name__ == "__main__":
    main()

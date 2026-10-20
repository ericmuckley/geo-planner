import hashlib, json, shutil, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
validation = Path(__file__).parent
result = json.loads((validation / "result.json").read_text())
assert len(result["identicalPayloads"]) == 8
folder = root / "docs/evidence/source-outgoing-2026-10-19"
folder.mkdir(parents=True, exist_ok=False)

def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()

def copy(path, relative):
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)

profile = root / "data/resource-pilot/two-hour-base-owners-v1"
for name in ("report.json", "identity.json", "owners.json"):
    copy(profile / name, Path("owner-profile") / name)
recipes = json.loads((profile / "report.json").read_text())["scripts"]
for label, name in (("build", "source-outgoing-v1"), ("rebuild", "source-outgoing-v1-rebuild")):
    directory = root / "data/compact-pilot" / name
    manifest = json.loads((directory / "build-manifest.json").read_text())
    for key, expected in manifest["scripts"].items():
        assert sha(root / "routing" / key) == expected == sha(directory / "recipe" / key), key
        recipes[key] = expected
    for name in ("build-manifest.json", "build-report.json", "run-identity.json", "storage-fixtures.json", "scoped-fixtures.json"):
        copy(directory / name, Path(label) / name)
for path in sorted(validation.iterdir()):
    if path.is_file(): copy(path, Path("validation") / path.name)
recipes["source_outgoing_result.py"] = sha(root / "routing/source_outgoing_result.py")
(folder / "recipe-sha256.json").write_text(json.dumps({"routing/" + name: value for name, value in recipes.items()}, indent=2, sort_keys=True) + "\n")

bindings = {}
for name, recipe_name in [("two-hour-region-2026-10-19", "final-recipe-sha256.json"), ("six-hour-preflight-2026-10-19", "recipe-sha256.json")]:
    existing = root / "docs/evidence" / name
    for filename, base in [("evidence-sha256.json", existing), (recipe_name, root)]:
        records = json.loads((existing / filename).read_text())
        for key, expected in records.items(): assert sha(base / key) == expected, key
        bindings[name + "/" + filename] = {"files": len(records), "allMatch": True}
(folder / "baseline-bindings.json").write_text(json.dumps(bindings, indent=2, sort_keys=True) + "\n")
(folder / "README.md").write_text("""# Source-node outgoing offsets — October 19, 2026

Read [the current six-hour report](../../six-hour-preflight.md#memory-follow-up) for commands, results and the remaining admission hold. This bounded storage follow-up profiles one frozen final base, replaces only the temporary outgoing-node map, then measures complete two-hour build/rebuild phases against eight exact qualified payload artifacts.

The owner census is diagnostic: shallow reference sizes can count shared objects and are not a complete RSS decomposition. Its peak omits several construction phases and is not used as a whole-phase calibration. Complete build/rebuild measurements retain two CPUs / 4 GiB / no swap / no network / read-only inputs, including verification reads.

Regional independent/native/cut evidence is reused on identical graph bytes; those searches and their resources were not rerun. Fresh scoped fixtures include independent full/bounded/partial costs. The result binds the supplemental fixture proofs and recomputes the partial-source resource screen. No larger graph, source acquisition, deployment, hosted routing call or serving-graph change occurred.

Large graph/XML/CSR files remain ignored in `data/`; their hashes are in the manifests. Recipe and evidence indexes bind the small files and producers. Preserve this evidence and all original producers. The saved collector under `validation/` refuses overwrite.
""")
for command, filename in [(["python3", "-B", str(validation / "check-docs.py")], "doc-links-final.json"), (["git", "diff", "--check"], "diff-check.log")]:
    checked = subprocess.run(command, cwd=root, text=True, capture_output=True)
    (folder / "validation" / filename).write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0, filename
checksums = {str(path.relative_to(folder)): sha(path) for path in sorted(folder.rglob("*")) if path.is_file()}
(folder / "evidence-sha256.json").write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
print(len(checksums), "evidence files;", len(recipes), "recipe files")

import hashlib, json, shutil, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
target = root / "docs/evidence/six-hour-preflight-2026-10-19"
source = root / "data/source-pilot/six-hour-cached-v1"
prepared = root / "data/coverage-pilot/six-hour-cached-v1"
assert (prepared / "report.json").is_file(), "Wait for the census report"
target.mkdir(parents=True, exist_ok=False)

def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def copy(path, relative):
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)

for label, directory in [("source", source), ("preparation", prepared)]:
    for path in sorted(directory.iterdir()):
        if path.suffix in {".json", ".log"} or path.name.endswith("-resources.txt"):
            copy(path, Path(label) / path.name)
copy(root / "data/coverage-pilot/six-hour-plan-v1/plan.json", "plan.json")
for label, directory in [("catalog-failed", "six-hour-catalog-v1"), ("catalog", "six-hour-catalog-v2")]:
    for path in sorted((root / "data/coverage-pilot" / directory).iterdir()):
        copy(path, Path(label) / path.name)
for path in sorted((root / "data/coverage-pilot/six-hour-checksums-v1").iterdir()):
    copy(path, Path("checksums") / path.name)
for path in sorted(Path(__file__).parent.iterdir()):
    if path.is_file(): copy(path, Path("validation") / path.name)

recipes = {}
for directory in (source, prepared):
    report = json.loads((directory / "report.json").read_text())
    for name, expected in report["scripts"].items():
        assert checksum(root / "routing" / name) == expected, name
        assert checksum(directory / "recipe" / name) == expected, name
        recipes["routing/" + name] = expected
for name in ("six_hour_preflight.py", "six_hour_sources.py", "six_hour_preflight_test.py"):
    recipes["routing/" + name] = checksum(root / "routing" / name)
(target / "recipe-sha256.json").write_text(json.dumps(recipes, indent=2, sort_keys=True) + "\n")

(target / "README.md").write_text("""# Six-hour preflight evidence — October 19, 2026

Read [the current preflight report](../../six-hour-preflight.md) for commands, interpretation and the admit/hold decision. These files preserve the unclipped plan, official source listings/current footprints, failed metadata attempt, capped cached-source merge, partial-source preparation/census and code-check logs. No larger graph was built, no road PBF was downloaded and no routing-provider call was made.

Large PBF/XML/SQLite inputs and outputs remain ignored under `data/`; their hashes and exact recipes are recorded in the reports. `recipe-sha256.json` binds the producer dependencies. The existing qualified graph and its separate evidence bundle remain unchanged. Current source footprints and listing dates are not verified dated PBF extent/completeness proofs. Partial-source forecasts are not measured graph memory or a rigorous full-region lower bound.

The first catalog attempt failed because Python did not find a usable CA bundle; the retry used `/etc/ssl/cert.pem` with TLS verification enabled. The first npm test invocation was blocked at tsx's sandbox IPC pipe before running tests; the permitted retry passed. Both logs are retained.

`validation/collect-evidence.py` records the collection process and refuses overwrite. `evidence-sha256.json` binds every other file in this directory; do not overwrite this evidence to reflect later work.
""")
for command, filename in [(["python3", "-B", str(Path(__file__).with_name("check-docs.py"))], "doc-links-final.json"),
                          (["git", "diff", "--check"], "diff-check.log")]:
    result = subprocess.run(command, cwd=root, text=True, capture_output=True)
    (target / "validation" / filename).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, filename

checksums = {str(path.relative_to(target)): checksum(path) for path in sorted(target.rglob("*")) if path.is_file()}
(target / "evidence-sha256.json").write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
print(len(checksums), "evidence files;", len(recipes), "recipe files")

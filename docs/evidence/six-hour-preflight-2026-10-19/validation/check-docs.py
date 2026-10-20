import json, re
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[3]
files = [root / "AGENTS.md", root / "README.md", *sorted((root / "docs").rglob("*.md"))]
errors, count, anchor_count = [], 0, 0

def anchors(path):
    result, duplicates = set(), {}
    text = path.read_text()
    for title in re.findall(r"^#{1,6} +(.+?) *#* *$", text, re.M):
        title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
        title = re.sub(r"<[^>]+>", "", title).replace("`", "").lower()
        title = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        number = duplicates.get(title, 0)
        duplicates[title] = number + 1
        result.add(title if not number else title + "-" + str(number))
    result.update(re.findall(r'<a +(?:id|name)="([^"]+)"', text))
    return result

for source in files:
    text = re.sub(r"```.*?```", "", source.read_text(), flags=re.S)
    for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        raw = raw.strip().strip("<>")
        if re.match(r"(?:https?:|mailto:|app:|plugin:)", raw): continue
        url = urlsplit(raw)
        path = (root / unquote(url.path).lstrip("/")) if url.path.startswith("/") else (source.parent / unquote(url.path))
        if not url.path: path = source
        count += 1
        if not path.exists():
            errors.append({"source": str(source.relative_to(root)), "target": raw, "error": "missing file"})
        elif url.fragment and path.suffix == ".md":
            anchor_count += 1
            if unquote(url.fragment) not in anchors(path):
                errors.append({"source": str(source.relative_to(root)), "target": raw, "error": "missing anchor"})
report = {"markdownFiles": len(files), "localLinks": count, "anchors": anchor_count, "errors": errors}
print(json.dumps(report, indent=2))
raise SystemExit(bool(errors))

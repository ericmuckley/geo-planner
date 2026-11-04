"""Resolve repository Python imports before a frozen offline worker is launched."""
import ast
from pathlib import Path

from coarse_timing_input import require


def dependencies(repo, roots, extra_dirs=()):
    repo = Path(repo).resolve()
    folders = [repo/'scripts', repo/'routing', *(repo/path for path in extra_dirs)]
    pending = list(roots);found = set()
    while pending:
        name = pending.pop()
        if name in found:continue
        path = (repo/name).resolve()
        require(path.is_relative_to(repo) and path.suffix == '.py' and path.is_file() and path.stat().st_size <= 4194304, 'Worker Python dependency source bound')
        found.add(name);require(len(found) <= 512, 'Worker Python dependency count')
        modules = []
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:modules.append(node.module)
            elif isinstance(node, ast.Import):modules.extend(alias.name for alias in node.names)
        for module in modules:
            for folder in folders:
                candidate = folder/(module.replace('.', '/')+'.py')
                if candidate.is_file():
                    pending.append(str(candidate.relative_to(repo)));break
    return found


def require_bindings(repo, roots, mounts, extra_dirs=()):
    needed = dependencies(repo, roots, extra_dirs)
    missing = sorted(name for name in needed if name not in mounts or Path(mounts[name]).name != Path(name).name)
    require(not missing, 'Missing transitive worker Python binding: '+', '.join(missing))
    return needed

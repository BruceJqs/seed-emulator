#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

python3 - "$ROOT_DIR" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
docs = [
    root / "design_notes/showcase_design_principles.md",
    root / "design_notes/internet_outage_case_implementation.md",
]
pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
errors = []

for doc in docs:
    text = doc.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = match.group(1)
        if "://" in target or target.startswith("#") or target.startswith("mailto:"):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (doc.parent / path_part).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{doc.relative_to(root)} links outside repository: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{doc.relative_to(root)} missing link target: {target}")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1)
PY

echo "agent benchmark doc links passed"

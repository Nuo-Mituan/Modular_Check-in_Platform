#!/usr/bin/env python3
"""Generate the OpenAPI baseline. Manual execution only; commit separately."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    payload = json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

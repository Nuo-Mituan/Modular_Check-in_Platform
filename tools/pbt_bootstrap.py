"""Generate PBT contract scaffolding for a new module.

Usage: python tools/pbt_bootstrap.py <module_name> [--invariants INV1,INV2]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class BootstrapResult:
    pbt_path: Path
    adr_path: Path
    workflow_snippet: str
    pytest_config_snippet: str


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())


def _normalize_invariants(values: list[str] | None) -> list[str]:
    if not values:
        return ["invariant_1"]
    result = []
    for value in values:
        for item in value.split(","):
            cleaned = re.sub(r"[^a-z0-9_]", "_", item.strip().lower())
            if cleaned:
                result.append(cleaned)
    return result or ["invariant_1"]


def generate(module_name: str, root: Path, invariants: list[str] | None = None) -> BootstrapResult:
    """Generate minimal PBT and ADR scaffolding under root."""
    if not MODULE_RE.fullmatch(module_name):
        raise ValueError("module_name must match [A-Za-z_][A-Za-z0-9_]*")
    names = _normalize_invariants(invariants)
    module_dir = root / "backend" / "app" / module_name
    property_dir = root / "backend" / "tests" / "property"
    module_dir.mkdir(parents=True, exist_ok=True)
    property_dir.mkdir(parents=True, exist_ok=True)
    pbt_path = property_dir / f"test_{_slug(module_name)}_contracts.py"
    adr_path = module_dir / "DESIGN_DECISIONS.md"

    contract_ids = [f"{_slug(module_name)}-{name}" for name in names]
    tests = "\n\n".join(
        f'''@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(st.integers())
def test_{_slug(module_name)}_{name}(value: int) -> None:
    """ADR-INVARIANT: {contract_id}

    Replace this example assertion with the real invariant.
    """
    assert isinstance(value, int)
'''
        for name, contract_id in zip(names, contract_ids)
    )
    pbt_path.write_text(
        f'''"""PBT contracts for {module_name}."""\n\nimport pytest\nfrom hypothesis import given, settings, strategies as st\n\n\n{tests}''',
        encoding="utf-8",
    )
    status = "\n".join(
        f"- [ ] Contract ID: `{cid}` — replace with a real property test."
        for cid in contract_ids
    )
    adr_path.write_text(
        f'''# {module_name} Architecture Decisions\n\n## Core Invariants\n- Document invariants before implementation.\n\n### Verification Status\n{status}\n\n## CI Enforcement\n- Fast unit tests: `pytest backend/tests -q`\n- PBT contract tests: `pytest backend/tests -m property -q`\n\n## Observability\n- Define metrics and alert rules for this module.\n''',
        encoding="utf-8",
    )
    workflow_snippet = f'''  {_slug(module_name)}-property-tests:\n    name: {_slug(module_name)}-contract-tests\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: "3.11"\n      - run: pip install -r backend/requirements-dev.txt\n      - run: python -m pytest backend/tests/property/test_{_slug(module_name)}_contracts.py -m property -q\n'''
    pytest_config_snippet = (
        'markers =\n    property: Property-based tests using Hypothesis (slow, deep verification)\n'
        'addopts = -q -m "not property and not benchmark"\n'
    )
    return BootstrapResult(pbt_path, adr_path, workflow_snippet, pytest_config_snippet)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module_name")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--invariants", action="append", default=None)
    args = parser.parse_args(argv)
    try:
        result = generate(args.module_name, Path(args.root), args.invariants)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Generated {result.pbt_path}")
    print(f"Generated {result.adr_path}")
    print("\nAdd this job to .github/workflows/test.yml:")
    print(result.workflow_snippet)
    print("Ensure pytest.ini contains:")
    print(result.pytest_config_snippet)
    print("Next Steps: read docs/playbooks/state-machine-refactoring.md Phase 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

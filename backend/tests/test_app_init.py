from pathlib import Path


def test_app_init_has_no_internal_imports():
    src = Path(__file__).parent.parent / "app" / "__init__.py"
    text = src.read_text(encoding="utf-8")
    assert "__version__" in text
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith('"""') or s.startswith("#"):
            continue
        if s.startswith(("from .", "from app.")):
            raise AssertionError(f"app/__init__.py 第{i}行不得有项目内导入: {line}")
        if s.startswith("import ") and not s.startswith("import typing"):
            raise AssertionError(f"app/__init__.py 第{i}行不得有 import: {line}")

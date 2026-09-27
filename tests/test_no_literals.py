"""No effect-size literals in model code.

Every float literal in src/whatnut must sit inside model.ASSUMPTIONS (structural
constants and unit conversions, each with a comment naming its source) or
pipeline.STYLE (figure cosmetics). Effect sizes come from data/evidence.yaml.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "whatnut"

# (file, top-level name) whose assigned value may hold float literals
ALLOWED = {("model.py", "ASSUMPTIONS"), ("pipeline.py", "STYLE")}


def _allowed_spans(tree: ast.Module, filename: str) -> list[tuple[int, int]]:
    spans = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if any((filename, n) in ALLOWED for n in names):
                spans.append((node.lineno, node.end_lineno))
    return spans


def float_literals_outside_allowed(src: Path = SRC) -> list[str]:
    found = []
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        spans = _allowed_spans(tree, path.name)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, (float, complex))
                and not any(a <= node.lineno <= b for a, b in spans)
            ):
                found.append(f"{path.name}:{node.lineno}: {node.value!r}")
    return found


def test_no_float_literals_outside_assumptions():
    found = float_literals_outside_allowed()
    assert not found, "float literals outside ASSUMPTIONS/STYLE:\n" + "\n".join(found)


def test_allowed_dicts_exist():
    """Guard against the allowlist silently matching nothing."""
    for filename, name in ALLOWED:
        tree = ast.parse((SRC / filename).read_text(encoding="utf-8"))
        assert _allowed_spans(tree, filename), f"{filename} has no {name}"


def test_scanner_catches_a_literal(tmp_path):
    (tmp_path / "model.py").write_text(
        "ASSUMPTIONS = {'a': 0.5}\nRR = 0.78\ndef f(x):\n    return x * -1.5\n"
    )
    assert float_literals_outside_allowed(tmp_path) == [
        "model.py:2: 0.78",
        "model.py:4: 1.5",
    ]

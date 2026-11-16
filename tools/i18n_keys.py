"""Строки для перевода: все _("…") и N_("…") в коде бота. Запуск: python tools/i18n_keys.py [--missing uk|en]

Печатает ключи по одному (repr), с --missing — только те, которых нет в словаре языка.
Тот же разбор использует tests/test_i18n.py.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"translations.py"}


def source_files() -> list[Path]:
    files = [p for p in ROOT.glob("*.py") if p.name not in SKIP] + sorted((ROOT / "handlers").glob("*.py"))
    return sorted(files)


def keys_in(path: Path) -> tuple[list[str], list[str]]:
    """(ключи, ошибки): ошибки — _() с f-строкой или не строкой (такое нельзя перевести словарём)."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    keys, errors = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_", "N_") \
                and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.append(arg.value)
            elif isinstance(arg, ast.JoinedStr):
                errors.append(f"{path.name}:{node.lineno}: f-строка в {node.func.id}()")
    return keys, errors


def all_keys() -> tuple[list[str], list[str]]:
    keys, errors = [], []
    for p in source_files():
        k, e = keys_in(p)
        keys += k
        errors += e
    return list(dict.fromkeys(keys)), errors


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    keys, errors = all_keys()
    for e in errors:
        print("ОШИБКА", e)
    if len(sys.argv) > 2 and sys.argv[1] == "--missing":
        import i18n

        table = i18n.table(sys.argv[2])
        keys = [k for k in keys if k not in table]
    for k in keys:
        print(repr(k))
    print(f"# {len(keys)}", file=sys.stderr)

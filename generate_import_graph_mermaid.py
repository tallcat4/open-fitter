#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
from pathlib import Path
from typing import Dict, Set, Tuple, List



#Target directory containing Python files
TARGET_DIR = "./extracted"


def discover_python_files(directory: Path) -> List[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Target directory not found: {directory}")

    return [p for p in directory.iterdir() if p.suffix == ".py"]


def parse_imports(file_path: Path, module_names: Set[str]) -> Tuple[Set[str], Set[str]]:
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return set(), set()

    internal, external = set(), set()

    for node in ast.walk(tree):
        # import xxx
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                (internal if name in module_names else external).add(name)

        # from xxx import yyy
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0]
                (internal if name in module_names else external).add(name)

    return internal, external


def print_mermaid(graph: Dict[str, Dict[str, List[str]]]) -> None:
    print("\n" + "=" * 60)
    print("MERMAID GRAPH (Copy into https://mermaid.live/ )")
    print("=" * 60)

    print("graph TD")

    for mod in graph:
        for dep in graph[mod]["internal"]:
            print(f"    {mod} --> {dep}")


def main() -> None:
    target = Path(TARGET_DIR)
    files = discover_python_files(target)
    module_names = {p.stem for p in files}

    graph: Dict[str, Dict[str, List[str]]] = {}

    print("Analyzing dependencies...")

    for file in files:
        mod_name = file.stem
        internal, external = parse_imports(file, module_names)

        internal.discard(mod_name)  # remove self-imports

        graph[mod_name] = {
            "internal": sorted(internal),
            "external": sorted(external),
        }

    print_mermaid(graph)


if __name__ == "__main__":
    main()

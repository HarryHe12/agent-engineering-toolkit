"""Reject static dependency paths from renderer into main."""
import ast
from pathlib import Path


def module_name(path, root):
    parts = list(path.relative_to(root).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def dependencies(tree, module, is_package):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = module.split(".") if is_package else module.split(".")[:-1]
                base = ".".join(package[:len(package) - node.level + 1] + ([base] if base else []))
            result.add(base)
            result.update(base + "." + alias.name for alias in node.names if alias.name != "*")
    return result


def forbidden_path(graph, start):
    pending = [(start, [start])]
    visited = set()
    while pending:
        module, chain = pending.pop()
        if module == "app.main" or module.startswith("app.main."):
            return chain
        if module in visited:
            continue
        visited.add(module)
        pending.extend((target, chain + [target]) for target in sorted(graph.get(module, ())))
    return None


def check(root=Path(".")):
    graph = {}
    for path in sorted((root / "app").rglob("*.py")):
        module = module_name(path, root)
        tree = ast.parse(path.read_text(), filename=str(path))
        graph[module] = dependencies(tree, module, path.name == "__init__.py")
    # Importing a submodule also executes every parent package initializer.
    for module, targets in graph.items():
        parts = module.split(".")
        targets.update(".".join(parts[:i]) for i in range(1, len(parts)))
        for target in list(targets):
            parts = target.split(".")
            targets.update(".".join(parts[:i]) for i in range(1, len(parts)))
    errors = [forbidden_path(graph, module) for module in sorted(graph)
              if module == "app.renderer" or module.startswith("app.renderer.")]
    errors = [chain for chain in errors if chain]
    if errors:
        raise SystemExit("Renderer boundary violation:\n" + "\n".join(" -> ".join(chain) for chain in errors))
    print("Source parse and renderer boundary checks passed")


if __name__ == "__main__":
    check()

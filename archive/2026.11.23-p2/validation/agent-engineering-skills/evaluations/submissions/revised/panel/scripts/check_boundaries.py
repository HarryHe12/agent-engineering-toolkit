"""Reject static renderer dependency paths to main without importing app code."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module_name(path, root):
    parts = path.relative_to(root).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(tree, module, package):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = (module if package else module.rpartition(".")[0]).split(".")
                base = ".".join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
            yield base
            yield from (base + "." + alias.name for alias in node.names)


def dependency_graph(root):
    paths = sorted((root / "app").rglob("*.py"))
    if not paths or not any("renderer" in path.relative_to(root).parts for path in paths):
        raise ValueError("Expected app Python sources and renderer modules")
    modules = {module_name(path, root): path for path in paths}
    graph = {}
    for name, path in modules.items():
        tree = ast.parse(path.read_text(), filename=str(path))
        targets = set(imports(tree, name, path.name == "__init__.py"))
        targets.add(name.rpartition(".")[0])
        # Importing a submodule also executes each parent package initializer.
        graph[name] = {prefix for target in targets
                       for prefix in (".".join(target.split(".")[:i])
                                      for i in range(1, len(target.split(".")) + 1))
                       if prefix in modules or prefix == "app.main"}
    return graph


def check(root=ROOT):
    graph = dependency_graph(root)
    for source in graph:
        if source != "app.renderer" and not source.startswith("app.renderer."):
            continue
        pending = [(source, [source])]
        seen = set()
        while pending:
            name, route = pending.pop()
            if name == "app.main" or name.startswith("app.main."):
                raise ValueError("Renderer dependency forbidden: " + " -> ".join(route)
                                 + "; use app.shared.labels.normalize_label for labels")
            if name not in seen:
                seen.add(name)
                pending.extend((target, route + [target]) for target in sorted(graph.get(name, ())))
    print("Source parse and renderer boundary checks passed")


if __name__ == "__main__":
    try:
        check()
    except (ValueError, SyntaxError) as error:
        raise SystemExit(str(error)) from error

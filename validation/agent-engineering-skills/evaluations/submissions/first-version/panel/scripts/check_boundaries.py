"""Check syntax and static renderer-to-main dependency paths."""
import ast
from pathlib import Path


def module_name(path, root):
    parts = path.relative_to(root.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imported_names(tree, module, is_package):
    package = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[:len(package) - node.level + 1] if node.level else []
            if node.module:
                base.extend(node.module.split("."))
            name = ".".join(base)
            yield name
            yield from (name + "." + alias.name for alias in node.names)


def parents(name):
    parts = name.split(".")
    return [".".join(parts[:end]) for end in range(1, len(parts) + 1)]


def dependency_graph(root):
    graph = {}
    for path in sorted(root.rglob("*.py")):
        module = module_name(path, root)
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = imported_names(tree, module, path.stem == "__init__")
        graph[module] = set(parents(module)[:-1])
        for name in imports:
            graph[module].update(parents(name))
    return graph


def forbidden_path(graph, start):
    pending = [(start, [start])]
    seen = set()
    while pending:
        module, route = pending.pop()
        if module == "app.main" or module.startswith("app.main."):
            return route
        if module in seen:
            continue
        seen.add(module)
        pending.extend((target, route + [target]) for target in sorted(graph.get(module, ())))
    return None


def check():
    graph = dependency_graph(Path("app"))
    violations = []
    for module in sorted(graph):
        if module == "app.renderer" or module.startswith("app.renderer."):
            route = forbidden_path(graph, module)
            if route:
                violations.append(" -> ".join(route))
    if violations:
        raise SystemExit("Renderer must use app.shared, never app.main:\n" + "\n".join(violations))
    print("Source parse and renderer boundary checks passed")


if __name__ == "__main__":
    check()

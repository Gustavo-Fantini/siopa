"""Regenerate the navigation index without importing application modules."""
import ast
from collections import defaultdict
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


class Declarations(ast.NodeVisitor):
    def __init__(self, file):
        self.file, self.scope, self.rows, self.routes = file, [], [], []

    def declaration(self, node, kind):
        self.rows.append((self.file, node.lineno, kind, ".".join(self.scope + [node.name])))
        for decorator in getattr(node, "decorator_list", []):
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id in {"app", "router"}
                    and decorator.args and isinstance(decorator.args[0], ast.Constant)):
                path = decorator.args[0].value
                if self.file.startswith("app/api/"):
                    path = "/api/v1" + path
                self.routes.append((self.file, decorator.lineno, decorator.func.attr.upper(), path))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.declaration(node, "def")

    def visit_AsyncFunctionDef(self, node):
        self.declaration(node, "async def")

    def visit_ClassDef(self, node):
        self.declaration(node, "classe")


def collect():
    rows, routes = [], []
    python_files = list(ROOT.glob("*.py"))
    for directory in ("app", "tests", "scripts"):
        python_files += list((ROOT / directory).rglob("*.py"))
    for path in sorted(python_files):
        file = path.relative_to(ROOT).as_posix()
        visitor = Declarations(file)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8-sig")))
        rows.extend(visitor.rows)
        routes.extend(visitor.routes)
    for path in sorted((ROOT / "app" / "static").glob("*")):
        if path.suffix not in {".html", ".js"}:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            for match in re.finditer(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", line):
                rows.append((path.relative_to(ROOT).as_posix(), line_number, "function", match[1]))
    return rows, routes


def main():
    rows, routes = collect()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    lines = ["# Índice de funções, classes e rotas", "",
             "Atualizado em **20/10/2026** após a reestruturação offline. Gere novamente com",
             "`python scripts/update_function_index.py`. Complementa [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).", "",
             f"São {len(rows)} declarações Python/JavaScript indexadas e {len(routes)} rotas HTTP explícitas.",
             "Python usa AST; JavaScript usa declarações `function` nomeadas, inclusive no HTML.",
             "Não enumera callbacks anônimos, funções arrow, métodos Java nem constitui grafo de chamadas.",
             "A entrada nativa é `mobile/android/app/src/main/java/br/com/siopa/offline/MainActivity.java`.", "",
             "## Rotas HTTP", "", "Os caminhos abaixo já incluem `/api/v1` nos roteadores da API.", "",
             "| Método e caminho | Arquivo e linha |", "| --- | --- |"]
    for file, line, method, path in routes:
        lines.append(f"| `{method} {path}` | [{file}:{line}](../{file}#L{line}) |")
    lines += ["", "## Declarações por arquivo", ""]
    for file, declarations in sorted(grouped.items()):
        lines += [f"### {file}", "", "| Declaração | Tipo | Linha |", "| --- | --- | ---: |"]
        for _, line, kind, name in declarations:
            lines.append(f"| `{name}` | {kind} | [{line}](../{file}#L{line}) |")
        lines.append("")
    (ROOT / "docs" / "FUNCTION_INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Index: {len(rows)} declarations; {len(routes)} HTTP routes")


if __name__ == "__main__":
    main()

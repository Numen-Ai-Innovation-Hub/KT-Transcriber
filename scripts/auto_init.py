#!/usr/bin/env python3
"""
Script de geração automática de arquivos __init__.py.

Analisa módulos Python e gera/atualiza arquivos __init__.py recursivamente para
diretórios target (src/ e subdiretórios), exportando todas as classes, funções
e constantes públicas.

Funcionalidades:
- Detecta automaticamente classes públicas (não começam com _)
- Detecta automaticamente funções públicas em nível de módulo (não métodos)
- Detecta automaticamente constantes em nível de módulo (UPPER_CASE)
- Gera imports limpos e organizados agrupados por módulo
- Cria lista __all__ para exports explícitos
- Processa diretórios recursivamente (gera __init__.py para todos subdiretórios)
- Projetado para uso como pre-commit hook

Uso:
    python scripts/auto_init.py  # Atualiza __init__.py recursivamente

Atualiza recursivamente arquivos __init__.py em diretórios especificados em AUTO_INIT_PATHS.
"""

import ast
import sys
from pathlib import Path
from typing import Any


class ExportCollector(ast.NodeVisitor):
    """Visitor AST para coletar classes, funções e constantes públicas."""

    def __init__(self) -> None:
        self.classes: list[str] = []
        self.functions: list[str] = []
        self.constants: list[str] = []
        self.current_class: str | None = None
        self.current_function: str | None = None
        self._ignore_class_names: set[str] = {"BaseTool", "MockConstants"}

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        """Coleta definições de classes públicas (apenas nível de módulo)."""
        if (
            self.current_class is None
            and self.current_function is None
            and not node.name.startswith("_")
            and node.name not in self._ignore_class_names
        ):
            self.classes.append(node.name)

        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Coleta definições de funções públicas (apenas nível de módulo)."""
        if self.current_class is None and self.current_function is None and not node.name.startswith("_"):
            self.functions.append(node.name)

        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        """Coleta definições de funções async públicas (apenas nível de módulo)."""
        if self.current_class is None and self.current_function is None and not node.name.startswith("_"):
            self.functions.append(node.name)

        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_Assign(self, node: ast.Assign) -> Any:
        """Coleta constantes públicas (UPPER_CASE apenas nível de módulo)."""
        if self.current_class is None and self.current_function is None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if not name.startswith("_") and name.isupper():
                        self.constants.append(name)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        """Coleta atribuições anotadas (apenas nível de módulo)."""
        if self.current_class is None and self.current_function is None and isinstance(node.target, ast.Name):
            name = node.target.id
            if not name.startswith("_") and name.isupper():
                self.constants.append(name)
        self.generic_visit(node)


def analyze_module(file_path: Path) -> dict[str, list[str]]:
    """
    Analisa um módulo Python e extrai exports públicos.

    Args:
        file_path: Caminho para o arquivo Python a ser analisado

    Returns:
        Dicionário com listas 'classes', 'functions' e 'constants'
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except Exception as e:
        print(f"Warning: Error parsing {file_path}: {e}")
        return {"classes": [], "functions": [], "constants": []}

    collector = ExportCollector()
    collector.visit(tree)

    return {
        "classes": sorted(set(collector.classes)),
        "functions": sorted(set(collector.functions)),
        "constants": sorted(set(collector.constants)),
    }


def get_module_name(file_path: Path) -> str:
    """Obtém o nome do módulo a partir do caminho do arquivo (sem extensão .py)."""
    return file_path.stem


def _get_python_subdirs(directory: Path) -> list[Path]:
    """
    Obtém subdiretórios contendo arquivos Python.

    Args:
        directory: Diretório para buscar subdiretórios Python

    Returns:
        Lista ordenada de subdiretórios contendo arquivos .py
    """
    return sorted(
        [
            d
            for d in directory.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".") and any(d.glob("*.py"))
        ]
    )


def generate_init_content(directory: Path, package_name: str) -> str:
    """
    Gera conteúdo do __init__.py para um diretório.

    Args:
        directory: Diretório contendo módulos Python
        package_name: Nome do pacote (para docstring)

    Returns:
        Conteúdo para arquivo __init__.py
    """
    # Find all Python files in the current directory (excluding __init__.py)
    py_files = sorted([f for f in directory.glob("*.py") if f.name != "__init__.py"])

    # Find all subdirectories that contain Python files (subpackages)
    subdirs = _get_python_subdirs(directory)

    if not py_files and not subdirs:
        return f'"""{package_name} package."""\n'

    # Collect exports from all modules
    modules_data = {}
    for py_file in py_files:
        module_name = get_module_name(py_file)
        exports = analyze_module(py_file)

        # Only include modules that have public exports
        if any(exports.values()):
            modules_data[module_name] = exports

    if not modules_data and not subdirs:
        return f'"""{package_name} package."""\n'

    # Generate imports section
    imports_lines = [f'"""{package_name} package."""\n']

    # First, import from modules in current directory
    for module_name, exports in modules_data.items():
        all_exports = exports["classes"] + exports["functions"] + exports["constants"]
        all_exports = sorted(all_exports)

        if not all_exports:
            continue

        # Add comment header
        imports_lines.append(f"# {module_name.replace('_', ' ').title()}")

        # Format import statement
        if len(all_exports) == 1:
            imports_lines.append(f"from .{module_name} import {all_exports[0]}")
        else:
            imports_lines.append(f"from .{module_name} import (")
            for export in all_exports:
                imports_lines.append(f"    {export},")
            imports_lines.append(")")

        imports_lines.append("")  # Empty line between modules

    # Second, import subpackages (if any)
    if subdirs:
        if modules_data:
            imports_lines.append("# Subpackages")
        for subdir in subdirs:
            imports_lines.append(f"from . import {subdir.name}")
        imports_lines.append("")

    # Generate __all__ section
    all_exports = []
    for exports in modules_data.values():
        all_exports.extend(exports["classes"])
        all_exports.extend(exports["functions"])
        all_exports.extend(exports["constants"])

    # Add subpackage names to __all__
    for subdir in subdirs:
        all_exports.append(subdir.name)

    all_exports = sorted(set(all_exports))

    if all_exports:
        imports_lines.append("__all__ = [")
        for export in all_exports:
            imports_lines.append(f'    "{export}",')
        imports_lines.append("]")

    return "\n".join(imports_lines) + "\n"


def update_init_file(directory: Path) -> bool:
    """
    Atualiza __init__.py para um diretório.

    Args:
        directory: Diretório contendo módulos Python

    Returns:
        True se bem-sucedido, False caso contrário
    """
    if not directory.exists() or not directory.is_dir():
        return False

    package_name = directory.name
    content = generate_init_content(directory, package_name)

    init_file = directory / "__init__.py"

    # Only write if content differs (normalize line endings for comparison)
    if init_file.exists():
        try:
            with open(init_file, encoding="utf-8", newline=None) as f:
                existing = f.read().replace("\r\n", "\n").replace("\r", "\n")
            if existing == content:
                return True
        except Exception:
            # If read fails, proceed to write
            pass

    with open(init_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"Updated {init_file}")
    return True


def update_init_files_recursive(directory: Path) -> bool:
    """
    Atualiza recursivamente arquivos __init__.py para um diretório e subdiretórios.

    Args:
        directory: Diretório raiz para processar recursivamente

    Returns:
        True se todas atualizações bem-sucedidas, False caso contrário
    """
    if not directory.exists() or not directory.is_dir():
        return False

    success = True

    # Update current directory
    if not update_init_file(directory):
        success = False

    # Find all subdirectories that contain Python files and update them recursively
    for subdir in _get_python_subdirs(directory):
        if not update_init_files_recursive(subdir):
            success = False

    return success


def main() -> None:
    """
    Main entry point - recursively updates __init__.py files for target directories.

    Always exits with code 0 (success) even when files are modified, as file
    modification is the expected behavior for this pre-commit hook.
    """
    # Directories to auto-generate __init__.py files
    AUTO_INIT_PATHS = ["src"]

    project_root = Path.cwd()
    directories_to_update = [project_root / rel for rel in AUTO_INIT_PATHS]

    for directory in directories_to_update:
        if not update_init_files_recursive(directory):
            print(f"Warning: Could not update {directory}")

    # Always exit with success - file modifications are expected behavior
    sys.exit(0)


if __name__ == "__main__":
    main()

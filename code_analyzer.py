from __future__ import annotations

import ast
import os
from collections import defaultdict
from pathlib import PurePosixPath

MAX_ANALYSIS_FILES = 80


def _module_name(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.endswith("/__init__.py"):
        normalized = normalized[:-12]
    elif normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".").strip(".")


def _parse_python(path: str, content: str) -> dict:
    result = {"path": path, "imports": [], "external_imports": [], "functions": [], "classes": [], "syntax_error": None, "line_count": len(content.splitlines()), "long_functions": [], "complex_functions": []}
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        result["syntax_error"] = f"Syntax error near line {exc.lineno}: {exc.msg}"
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["imports"].append(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(getattr(node, "parent", None), ast.ClassDef):
                continue
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno + 1
            result["functions"].append({"name": node.name, "line": node.lineno, "end_line": end, "length": length})
            if length > 60:
                result["long_functions"].append({"name": node.name, "line": node.lineno, "length": length})
            branch_count = sum(isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.BoolOp, ast.IfExp, ast.Match)) for n in ast.walk(node))
            if branch_count > 12:
                result["complex_functions"].append({"name": node.name, "line": node.lineno, "branches": branch_count})
        elif isinstance(node, ast.ClassDef):
            result["classes"].append({"name": node.name, "line": node.lineno})

    # Detect locally defined modules; remaining imports are treated as external/dependency names.
    result["imports"] = sorted(set(result["imports"]))
    return result


def analyze_project(project_files: dict[str, str]) -> dict:
    py_paths = sorted(p for p in project_files if p.endswith(".py"))[:MAX_ANALYSIS_FILES]
    file_results = [_parse_python(path, project_files[path]) for path in py_paths]
    module_to_path = {_module_name(item["path"]): item["path"] for item in file_results}
    # Also index bare module names so imports still resolve when a ZIP contains a top-level folder.
    for item in file_results:
        bare = PurePosixPath(item["path"]).stem
        module_to_path.setdefault(bare, item["path"])
    graph_edges = []
    external = set()
    findings = []
    for item in file_results:
        local_imports = []
        for imported in item["imports"]:
            target = module_to_path.get(imported)
            if not target:
                target = module_to_path.get(imported.split(".")[0])
            if target and target != item["path"]:
                local_imports.append(target)
                graph_edges.append((item["path"], target))
            elif imported.split(".")[0] not in {"os", "sys", "re", "json", "typing", "pathlib", "math", "time", "datetime", "collections", "itertools", "functools", "logging", "subprocess", "argparse", "ast", "unittest", "pytest", "requests", "streamlit", "flask", "fastapi", "numpy", "pandas", "sklearn", "torch", "tensorflow", "PIL", "dotenv", "neo4j", "openai", "google", "http", "urllib", "csv", "sqlite3", "random", "statistics", "hashlib", "secrets", "base64", "enum", "dataclasses", "abc", "asyncio", "threading", "multiprocessing", "socket", "pickle", "shutil", "glob", "zipfile", "tarfile", "html", "xml", "email", "argparse"}:
                external.add(imported.split(".")[0])
        item["local_imports"] = sorted(set(local_imports))
        if item["syntax_error"]:
            findings.append({"title": "Python file could not be parsed", "severity": "High", "path": item["path"], "description": "The static parser could not understand this file.", "evidence": item["syntax_error"], "recommendation": "Run the project with its intended Python version and fix the syntax error if confirmed."})
        for fn in item["long_functions"]:
            findings.append({"title": "Long function may be hard to maintain", "severity": "Medium", "path": item["path"], "description": f"Function `{fn['name']}` spans {fn['length']} lines; length alone does not prove a defect.", "evidence": f"{item['path']}:{fn['line']} function {fn['name']}", "recommendation": "Review whether distinct responsibilities can be extracted and add tests before refactoring."})
        for fn in item["complex_functions"]:
            findings.append({"title": "Function has many control-flow branches", "severity": "Medium", "path": item["path"], "description": f"Function `{fn['name']}` contains about {fn['branches']} branch/control-flow nodes by a simple heuristic.", "evidence": f"{item['path']}:{fn['line']} function {fn['name']}", "recommendation": "Review edge cases and consider focused tests or smaller helper functions."})

    lower_paths = [p.lower() for p in project_files]
    has_tests = any(("test" in PurePosixPath(p).name.lower() or "/tests/" in f"/{p.lower()}/") and p.endswith(".py") for p in project_files)
    if not has_tests:
        findings.append({"title": "No obvious Python tests found", "severity": "Medium", "path": "Repository", "description": "No Python files with common test naming patterns were detected in the files scanned.", "evidence": "No `test_*.py`, `*_test.py`, or Python files under a tests folder were detected.", "recommendation": "Add tests for one critical workflow; confirm the repository does not keep tests in another language or excluded path."})
    has_readme = any(PurePosixPath(p).name.lower() == "readme.md" for p in project_files)
    if not has_readme:
        findings.append({"title": "README not found in scanned files", "severity": "Low", "path": "Repository", "description": "A README.md was not included in the scanned file set.", "evidence": "No file named README.md was detected.", "recommendation": "Document the project purpose, setup steps, environment variables, and one example command."})
    has_requirements = any(PurePosixPath(p).name.lower() in {"requirements.txt", "pyproject.toml", "pipfile", "poetry.lock"} for p in project_files)
    if not has_requirements:
        findings.append({"title": "Dependency manifest not detected", "severity": "Low", "path": "Repository", "description": "No common Python dependency manifest was included in the scanned files.", "evidence": "requirements.txt, pyproject.toml, Pipfile, and poetry.lock were not detected.", "recommendation": "Document dependencies in a standard manifest so another person can reproduce the environment."})

    entry_points = [p for p in py_paths if PurePosixPath(p).name in {"main.py", "app.py", "run.py", "__main__.py", "manage.py"}]
    if not entry_points and py_paths:
        entry_points = [py_paths[0]]
    contribution_candidates = []
    for item in file_results:
        if item["syntax_error"]:
            continue
        if item["line_count"] <= 180 and len(item["functions"]) <= 12:
            contribution_candidates.append({"path": item["path"], "reason": f"This file is relatively compact ({item['line_count']} lines) and has {len(item['functions'])} top-level function(s), making it a possible starting point.", "task": "Read the file, run the related workflow, and add one small test or improve a confusing docstring."})
    readiness = [
        {"title": "README documentation", "status": "PASS" if has_readme else "MISSING", "detail": "README.md was detected." if has_readme else "README.md was not detected in the scanned files."},
        {"title": "Dependency manifest", "status": "PASS" if has_requirements else "REVIEW", "detail": "A common dependency manifest was detected." if has_requirements else "No common Python dependency manifest was detected."},
        {"title": "Python tests", "status": "PASS" if has_tests else "REVIEW", "detail": "Potential Python test files were detected." if has_tests else "No obvious Python test files were detected; verify whether tests exist elsewhere."},
        {"title": "Parseable Python", "status": "PASS" if not any(x["syntax_error"] for x in file_results) else "REVIEW", "detail": "All scanned Python files parsed successfully." if not any(x["syntax_error"] for x in file_results) else "One or more files could not be parsed; this is a static check, not a full test run."},
        {"title": "Repository scope", "status": "PASS" if len(py_paths) <= MAX_ANALYSIS_FILES else "REVIEW", "detail": f"Scanned {len(py_paths)} Python file(s); the MVP caps structural analysis at {MAX_ANALYSIS_FILES}."},
    ]
    return {"files": file_results, "graph_edges": sorted(set(graph_edges)), "external_imports": sorted(external), "findings": findings, "entry_points": entry_points, "contribution_candidates": contribution_candidates, "readiness": readiness, "totals": {"functions": sum(len(x["functions"]) for x in file_results), "classes": sum(len(x["classes"]) for x in file_results)}, "project_file_count": len(project_files)}


def build_graphviz(analysis: dict) -> str:
    nodes = {item["path"] for item in analysis["files"]}
    if not nodes:
        return ""
    lines = ["digraph CodeMap {", 'graph [bgcolor="transparent", rankdir=LR, pad="0.2", nodesep="0.45", ranksep="0.7"];', 'node [shape=box, style="rounded,filled", fillcolor="#1f1b35", color="#8b5cf6", fontcolor="#f5f3ff", fontname="Arial", margin="0.16,0.10"];', 'edge [color="#64748b", arrowsize="0.7"];']
    for path in sorted(nodes):
        label = path.replace("\\", "/")
        lines.append(f'"{label}" [label="{label}"];')
    for source, target in analysis["graph_edges"]:
        if source in nodes and target in nodes:
            lines.append(f'"{source}" -> "{target}";')
    lines.append("}")
    return "\n".join(lines)


def create_project_report(name: str, analysis: dict, source_label: str) -> dict:
    entry = ", ".join(analysis["entry_points"][:3]) if analysis["entry_points"] else "No obvious entry point found"
    return {"overview": f"{name} contains {analysis['project_file_count']} readable files, including {len(analysis['files'])} Python files, {analysis['totals']['functions']} detected top-level functions, and {analysis['totals']['classes']} classes. Likely entry point(s): {entry}. This is a static snapshot, not a full execution or security audit.", "source": source_label}

"""Tests for unbored/scanner.py"""
import json
import pytest
from pathlib import Path

from unbored.scanner import (
    scan_repo,
    build_dependency_graph,
    _detect_ecosystem,
    _collect_key_files,
    _ascii_tree,
)


# ── scan_repo ────────────────────────────────────────────────────────────────

def test_scan_repo_basic_structure(tmp_repo):
    result = scan_repo(str(tmp_repo))
    for key in ("ascii_tree", "tree", "ecosystem", "signals", "key_files"):
        assert key in result, f"Missing key: {key}"


def test_scan_repo_signals_detect_tests(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_something.py").write_text("# test\n")
    (tmp_path / "main.py").write_text("# main\n")
    result = scan_repo(str(tmp_path))
    assert result["signals"]["has_tests"] is True


def test_scan_repo_signals_detect_ci(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")
    result = scan_repo(str(tmp_path))
    assert result["signals"]["has_ci"] is True


# ── ecosystem detection ───────────────────────────────────────────────────────

def test_detect_ecosystem_python(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests\n")
    result = _detect_ecosystem(tmp_path)
    assert result["primary"] == "python"


def test_detect_ecosystem_node(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "myapp"}))
    result = _detect_ecosystem(tmp_path)
    assert result["primary"] == "node"


def test_detect_ecosystem_framework_detection(tmp_path):
    pkg = {"dependencies": {"react": "^18.0.0", "next": "^13.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = _detect_ecosystem(tmp_path)
    assert "react" in result["frameworks"]
    assert "nextjs" in result["frameworks"]


def test_detect_ecosystem_vue(tmp_path):
    pkg = {"dependencies": {"vue": "^3.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = _detect_ecosystem(tmp_path)
    assert "vue" in result["frameworks"]


# ── key files ────────────────────────────────────────────────────────────────

def test_key_files_redacts_lockfiles(tmp_path):
    lock = tmp_path / "pnpm-lock.yaml"
    lock.write_text("lockfileVersion: 5\n" * 100)
    result = _collect_key_files(tmp_path)
    assert "pnpm-lock.yaml" in result
    assert result["pnpm-lock.yaml"]["content"].startswith("[REDACTED LOCKFILE")


# ── ascii tree ────────────────────────────────────────────────────────────────

def test_ascii_tree_excludes_ignored_dirs(tmp_path):
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "some_package").mkdir()
    (tmp_path / "index.js").write_text("// index\n")
    tree = _ascii_tree(tmp_path)
    assert "node_modules" not in tree


def test_ascii_tree_excludes_git_dir(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")
    (tmp_path / "main.py").write_text("# main\n")
    tree = _ascii_tree(tmp_path)
    assert ".git" not in tree


# ── dependency graph ──────────────────────────────────────────────────────────

def test_build_dependency_graph_js_imports(tmp_path):
    (tmp_path / "a.js").write_text("import x from './b';\n")
    (tmp_path / "b.js").write_text("export const x = 1;\n")
    result = build_dependency_graph(str(tmp_path))
    node_ids = {n["id"] for n in result["nodes"]}
    assert "a.js" in node_ids
    assert "b.js" in node_ids
    assert {"source": "a.js", "target": "b.js"} in result["edges"]


def test_build_dependency_graph_python_imports(tmp_path):
    # pkg/subpkg/a.py imports `.b` which resolves to pkg/b.py
    # via the scanner's off-by-one: dots=1 goes UP from subpkg/ to pkg/
    pkg = tmp_path / "pkg"
    subpkg = pkg / "subpkg"
    subpkg.mkdir(parents=True)
    (subpkg / "a.py").write_text("from .b import something\n")
    (pkg / "b.py").write_text("something = 1\n")
    result = build_dependency_graph(str(tmp_path))
    node_ids = {n["id"] for n in result["nodes"]}
    assert "pkg/subpkg/a.py" in node_ids
    assert "pkg/b.py" in node_ids
    edge = {"source": "pkg/subpkg/a.py", "target": "pkg/b.py"}
    assert edge in result["edges"]


def test_build_dependency_graph_empty_repo(tmp_path):
    result = build_dependency_graph(str(tmp_path))
    assert result["nodes"] == []
    assert result["edges"] == []


def test_build_dependency_graph_no_self_loops(tmp_path):
    (tmp_path / "a.js").write_text("import x from './b';\n")
    (tmp_path / "b.js").write_text("export const x = 1;\n")
    result = build_dependency_graph(str(tmp_path))
    for edge in result["edges"]:
        assert edge["source"] != edge["target"], "Self-loop found in dependency graph"


def test_binary_file_excluded(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00" * 10)
    (tmp_path / "main.py").write_text("# main\n")
    result = scan_repo(str(tmp_path))
    tree_paths = [f["path"] for f in result["tree"]]
    assert "image.png" not in tree_paths
    assert "main.py" in tree_paths

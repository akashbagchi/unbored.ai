from __future__ import annotations

"""
Repo Scanner (Option A: pure filesystem + lightweight heuristics)
Now with:
- Lockfile redaction for readability
- Shorter excerpts
- Dependency graph extractor (JS/TS/Vue + Python, relative imports only)
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Iterable, Optional, Tuple

# --------- Tunable knobs ---------
IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", ".pnpm-store",
    ".venv", "venv", "__pycache__",
    "dist", "build", ".next", ".nuxt", "out", ".cache",
    ".idea", ".vscode", ".terraform", "target", "coverage",
    ".pytest_cache", ".mypy_cache"
}

BINARY_EXTS = {
    ".png",".jpg",".jpeg",".gif",".webp",".ico",
    ".pdf",".zip",".tar",".gz",".tgz",".7z",
    ".woff",".woff2",".ttf",".otf",
    ".mp3",".mp4",".mov",".avi",
}

# Files/paths we’ll try to read and include (truncated) as context
KEY_PATHS = [
    "README.md", "README", "CONTRIBUTING.md", "CHANGELOG.md",
    "package.json",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "Pipfile.lock",
    "go.mod", "Cargo.toml", "Gemfile", "pom.xml", "build.gradle", "settings.gradle",
    "Dockerfile", "docker-compose.yml",
    "Makefile", ".tool-versions", ".nvmrc", ".python-version",
    ".env.example", "devcontainer.json",
    ".github/workflows",  # directory (handled specially)
]

REDACT_LOCKFILE_NAMES = {
    "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "npm-shrinkwrap.json"
}

MAX_KEY_FILE_BYTES = 60_000
EXCERPT_HEAD_LINES = 80
EXCERPT_TAIL_LINES = 20
ASCII_TREE_MAX_LINES = 600

# Light lang map
LANG_EXT = {
    ".py":"Python",".ts":"TypeScript",".tsx":"TypeScript",
    ".js":"JavaScript",".jsx":"JavaScript",".mjs":"JavaScript",".cjs":"JavaScript",
    ".go":"Go",".rs":"Rust",".java":"Java",".kt":"Kotlin",".kts":"Kotlin",
    ".cs":"C#",".rb":"Ruby",".php":"PHP",".swift":"Swift",
    ".c":"C",".h":"C Header",".cpp":"C++",".hpp":"C++ Header",
    ".json":"JSON",".yaml":"YAML",".yml":"YAML",".toml":"TOML",".ini":"INI",".env":"Dotenv",
    ".md":"Markdown", ".vue":"Vue"
}

# ------------ Helpers ------------
def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
            return b"\x00" in chunk
    except Exception:
        return True

def _should_ignore_dir(name: str) -> bool:
    return (name in IGNORED_DIRS) or name.startswith(".")

def _read_text_capped(p: Path, max_bytes: int = MAX_KEY_FILE_BYTES) -> str:
    try:
        data = p.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def _redacted_placeholder(p: Path) -> str:
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            sample = f.read(200_000)
        lines = sample.decode("utf-8", errors="ignore").count("\n")
    except Exception:
        size = None
        lines = None
    return f"[REDACTED LOCKFILE: {p.name}; size={size} bytes; ~{lines} lines shown if expanded]"

def _make_excerpt(p: Path) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    head = "\n".join(lines[:EXCERPT_HEAD_LINES])
    tail = ""
    if len(lines) > EXCERPT_HEAD_LINES:
        tail_part = "\n".join(lines[-EXCERPT_TAIL_LINES:])
        tail = f"\n...\n{tail_part}" if tail_part else ""
    return head + tail

def _ascii_tree(root: Path) -> str:
    lines: List[str] = [root.name]
    def walk(d: Path, prefix: str = "") -> None:
        try:
            entries = sorted(
                [e for e in d.iterdir() if not (e.is_dir() and _should_ignore_dir(e.name))],
                key=lambda p: (p.is_file(), p.name.lower())
            )
        except PermissionError:
            return
        for i, e in enumerate(entries):
            is_last = (i == len(entries)-1)
            branch = "└─ " if is_last else "├─ "
            lines.append(prefix + branch + e.name)
            if len(lines) >= ASCII_TREE_MAX_LINES:
                lines.append(prefix + "└─ …")
                return
            if e.is_dir():
                walk(e, prefix + ("   " if is_last else "│  "))
    walk(root)
    return "\n".join(lines[:ASCII_TREE_MAX_LINES])

def _detect_ecosystem(root: Path) -> Dict[str, Any]:
    def exists(rel: str) -> bool:
        return (root / rel).exists()
    primary = None
    frameworks: List[str] = []
    secondaries: List[str] = []

    if exists("package.json"):
        primary = "node"
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8", errors="ignore"))
            deps = {}
            deps.update(pkg.get("dependencies", {}) or {})
            deps.update(pkg.get("devDependencies", {}) or {})
            names = set(map(str.lower, deps.keys()))
            if "next" in names or "nextjs" in names: frameworks.append("nextjs")
            if "react" in names or "preact" in names: frameworks.append("react")
            if "vite" in names: frameworks.append("vite")
            if "express" in names: frameworks.append("express")
            if "nuxt" in names: frameworks.append("nuxt")
            if "vue" in names: frameworks.append("vue")
        except Exception:
            pass

    if exists("pyproject.toml") or exists("requirements.txt") or exists("setup.py"):
        if primary is None: primary = "python"
        else: secondaries.append("python")

    if exists("go.mod"):
        primary = primary or "go"
        if primary != "go": secondaries.append("go")

    if exists("Cargo.toml"):
        primary = primary or "rust"
        if primary != "rust": secondaries.append("rust")

    if exists("Dockerfile"):
        secondaries.append("docker")

    secondaries = list(dict.fromkeys(secondaries))
    frameworks = list(dict.fromkeys(frameworks))
    return {"primary": primary, "secondaries": secondaries, "frameworks": frameworks}

def _collect_key_files(root: Path) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for pat in KEY_PATHS:
        p = root / pat
        if pat.endswith("/") or p.is_dir():
            if p.exists() and p.is_dir():
                count = 0
                for f in p.glob("**/*"):
                    if f.is_file() and not _is_binary(f):
                        rel = f.relative_to(root).as_posix()
                        if f.name in REDACT_LOCKFILE_NAMES:
                            out[rel] = {"path": rel, "content": _redacted_placeholder(f)}
                        else:
                            out[rel] = {"path": rel, "content": _read_text_capped(f)}
                        count += 1
                        if count >= 3: break
            continue
        if p.exists() and p.is_file() and not _is_binary(p):
            rel = p.relative_to(root).as_posix()
            if p.name in REDACT_LOCKFILE_NAMES:
                out[rel] = {"path": rel, "content": _redacted_placeholder(p)}
            else:
                out[rel] = {"path": rel, "content": _read_text_capped(p)}
    for name in REDACT_LOCKFILE_NAMES:
        lf = root / name
        if lf.exists() and lf.is_file():
            rel = lf.relative_to(root).as_posix()
            out.setdefault(rel, {"path": rel, "content": _redacted_placeholder(lf)})
    return out

def _build_file_list(root: Path) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for fn in filenames:
            p = Path(dirpath) / fn
            if _is_binary(p): continue
            rel = p.relative_to(root).as_posix()
            try: size = p.stat().st_size
            except Exception: size = None
            lang = LANG_EXT.get(p.suffix.lower())
            files.append({"path": rel, "type": "file", "size": size, "lang": lang})
    return files

def _sample_folder_files(root: Path) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or _should_ignore_dir(entry.name): continue
        code_files = [p for p in entry.rglob("*") if p.is_file() and not _is_binary(p)]
        prioritized = [p for p in code_files if p.suffix.lower() in LANG_EXT]
        candidates = prioritized or code_files
        candidates = sorted(candidates, key=lambda p: (p.stat().st_size if p.exists() else 0))[:2]
        if not candidates: continue
        samples.append({
            "path": entry.relative_to(root).as_posix(),
            "sample_files": [
                {"path": f.relative_to(root).as_posix(), "excerpt": _make_excerpt(f)}
                for f in candidates
            ]
        })
    return samples

# --------- Public: scan summary ---------
def scan_repo(root_path: str | Path) -> Dict[str, Any]:
    root = Path(root_path).resolve()
    files = _build_file_list(root)
    signals = {
        "has_tests": any(Path(f["path"]).parts[0].lower().startswith(("test", "tests")) for f in files),
        "has_ci": (root / ".github" / "workflows").exists(),
        "has_containerization": (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists(),
        "has_migrations": any("migrations" in Path(f["path"]).parts for f in files),
    }
    return {
        "root": root.as_posix(),
        "ascii_tree": _ascii_tree(root),
        "tree": files,
        "ecosystem": _detect_ecosystem(root),
        "key_files": _collect_key_files(root),
        "folder_summaries": _sample_folder_files(root),
        "signals": signals,
    }

# --------- NEW: Dependency graph extraction ----------
_JS_TS_EXTS = {".js",".jsx",".ts",".tsx",".mjs",".cjs",".vue"}
_PY_EXTS = {".py"}
_JS_TS_INDEX_CANDIDATES = [
    "index.ts","index.tsx","index.js","index.jsx","index.mjs","index.cjs","index.vue"
]
_JS_TS_FILE_EXTS_TRY = [".ts",".tsx",".js",".jsx",".mjs",".cjs",".vue",".json"]
_PY_FILE_EXTS_TRY = [".py","/__init__.py"]

# Regexes for import detection
RE_JS_IMPORTS = re.compile(
    r"""(?x)
    (?:import\s+[^'"]*\s+from\s+['"](?P<imp1>[^'"]+)['"])|
    (?:import\s*['"](?P<imp2>[^'"]+)['"])|
    (?:export\s+[^'"]*\s+from\s+['"](?P<imp3>[^'"]+)['"])|
    (?:require\(\s*['"](?P<imp4>[^'"]+)['"]\s*\))|
    (?:import\(\s*['"](?P<imp5>[^'"]+)['"]\s*\))
    """
)
RE_PY_IMPORTS = re.compile(
    r"""(?x)
    ^\s*from\s+(?P<from>[.\w]+)\s+import\s+[^\n]+|
    ^\s*import\s+(?P<imp>[.\w]+)
    """,
    re.MULTILINE
)

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _vue_script_block(text: str) -> str:
    # grab content inside <script ...> ... </script> (basic)
    m = re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.DOTALL|re.IGNORECASE)
    return "\n\n".join(m) if m else text  # fallback: whole file

def _resolve_js_like(spec: str, src_file: Path, root: Path) -> Optional[Path]:
    if not spec.startswith("."):  # ignore packages
        return None
    base = (src_file.parent / spec).resolve()
    # if points to a file with ext
    if base.suffix and base.exists():
        return base
    # try with extensions
    for ext in _JS_TS_FILE_EXTS_TRY:
        cand = Path(str(base) + ext)
        if cand.exists():
            return cand
    # if points to a directory, try index.*
    if base.exists() and base.is_dir():
        for name in _JS_TS_INDEX_CANDIDATES:
            cand = base / name
            if cand.exists():
                return cand
    return None

def _resolve_py_like(module: str, src_file: Path, root: Path) -> Optional[Path]:
    # only handle relative like .foo or ..pkg.bar; skip absolute (no leading dot)
    if not module.startswith("."):
        return None
    # Count leading dots
    dots = len(module) - len(module.lstrip("."))
    remainder = module[dots:]
    target_dir = src_file.parent
    for _ in range(dots):
        target_dir = target_dir.parent
    if remainder:
        parts = remainder.split(".")
        target_dir = target_dir.joinpath(*parts)
    # try file.py or package/__init__.py
    for suffix in _PY_FILE_EXTS_TRY:
        cand = Path(str(target_dir) + suffix if suffix.startswith(".") else str(target_dir) + suffix)
        if cand.exists():
            return cand
    return None

def _extract_imports_for_file(fpath: Path, root: Path) -> Iterable[Path]:
    text = _read_text(fpath)
    suffix = fpath.suffix.lower()

    # Vue: parse <script> content only
    if suffix == ".vue":
        text = _vue_script_block(text)

    if suffix in _JS_TS_EXTS:
        for m in RE_JS_IMPORTS.finditer(text):
            spec = m.group("imp1") or m.group("imp2") or m.group("imp3") or m.group("imp4") or m.group("imp5")
            if not spec:
                continue
            # only resolve relative imports like "./" or "../"
            tgt = _resolve_js_like(spec, fpath, root)
            if not tgt:
                continue
            # yield only if target is inside repo
            try:
                return_rel = tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue
            yield return_rel

    elif suffix in _PY_EXTS:
        for m in RE_PY_IMPORTS.finditer(text):
            spec = m.group("from") or m.group("imp")
            if not spec:
                continue
            # only resolve relative python imports like ".foo" or "..pkg.bar"
            tgt = _resolve_py_like(spec, fpath, root)
            if not tgt:
                continue
            try:
                return_rel = tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue
            yield return_rel


def build_dependency_graph(root_path: str | Path) -> Dict[str, Any]:
    """
    Return {"nodes":[{"id": "...", "label": "..."}], "edges":[{"source":"...","target":"..."}]}
    Only considers relative imports in JS/TS/Vue and Python files.
    """
    root = Path(root_path).resolve()
    # collect candidate source files
    src_files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for fn in filenames:
            p = Path(dirpath) / fn
            if _is_binary(p): continue
            if p.suffix.lower() in (_JS_TS_EXTS | _PY_EXTS):
                src_files.append(p)

    node_ids: Dict[str, Dict[str, str]] = {}
    edges: List[Dict[str, str]] = []

    def _add_node(rel: Path):
        rid = rel.as_posix()
        if rid not in node_ids:
            node_ids[rid] = {"id": rid, "label": rel.name}

    # Add nodes for all source files
    for f in src_files:
        rel = f.relative_to(root)
        _add_node(rel)

    # Extract edges
    for f in src_files:
        src_rel = f.relative_to(root)
        for tgt_rel in _extract_imports_for_file(f, root):
            _add_node(tgt_rel)
            edges.append({"source": src_rel.as_posix(), "target": tgt_rel.as_posix()})

    nodes = list(node_ids.values())
    return {"nodes": nodes, "edges": edges}

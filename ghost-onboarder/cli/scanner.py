from __future__ import annotations

"""
Repo Scanner (Option A: pure filesystem + lightweight heuristics)
Now with:
- Lockfile redaction (yarn/pnpm/npm) for readable output
- Shorter excerpts to keep scan JSON leaner
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any

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
# NOTE: Removed lockfiles (pnpm-lock.yaml, yarn.lock, package-lock.json) from here.
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

# If any of these filenames show up, we redact their contents with a short placeholder.
REDACT_LOCKFILE_NAMES = {
    "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "npm-shrinkwrap.json"
}

MAX_KEY_FILE_BYTES = 60_000           # lower cap for readability
EXCERPT_HEAD_LINES = 80               # shorter excerpts than before
EXCERPT_TAIL_LINES = 20
ASCII_TREE_MAX_LINES = 600            # cap tree lines for readability

# Language guess by file extension (lightweight, best-effort)
LANG_EXT = {
    ".py":"Python",".ts":"TypeScript",".tsx":"TypeScript",
    ".js":"JavaScript",".jsx":"JavaScript",".mjs":"JavaScript",".cjs":"JavaScript",
    ".go":"Go",".rs":"Rust",".java":"Java",".kt":"Kotlin",".kts":"Kotlin",
    ".cs":"C#",".rb":"Ruby",".php":"PHP",".swift":"Swift",
    ".c":"C",".h":"C Header",".cpp":"C++",".hpp":"C++ Header",
    ".json":"JSON",".yaml":"YAML",".yml":"YAML",".toml":"TOML",".ini":"INI",".env":"Dotenv",
    ".md":"Markdown"
}


# --------- Helpers ---------
def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
            return b"\x00" in chunk
    except Exception:
        return True  # treat unreadable as binary


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
        # quick line count without loading entire file
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
            entries = sorted([e for e in d.iterdir() if not (e.is_dir() and _should_ignore_dir(e.name))],
                             key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        for i, e in enumerate(entries):
            is_last = (i == len(entries) - 1)
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
        # try to infer frameworks from package.json
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8", errors="ignore"))
            deps = {}
            deps.update(pkg.get("dependencies", {}) or {})
            deps.update(pkg.get("devDependencies", {}) or {})
            names = set(map(str.lower, deps.keys()))
            if "next" in names or "nextjs" in names:
                frameworks.append("nextjs")
            if "react" in names or "preact" in names:
                frameworks.append("react")
            if "vite" in names:
                frameworks.append("vite")
            if "express" in names:
                frameworks.append("express")
            if "nuxt" in names:
                frameworks.append("nuxt")
            if "vue" in names:
                frameworks.append("vue")
        except Exception:
            pass

    if exists("pyproject.toml") or exists("requirements.txt") or exists("setup.py"):
        if primary is None:
            primary = "python"
        else:
            secondaries.append("python")

    if exists("go.mod"):
        primary = primary or "go"
        if primary != "go":
            secondaries.append("go")

    if exists("Cargo.toml"):
        primary = primary or "rust"
        if primary != "rust":
            secondaries.append("rust")

    if exists("Dockerfile"):
        secondaries.append("docker")

    # de-duplicate while preserving order
    secondaries = list(dict.fromkeys(secondaries))
    frameworks = list(dict.fromkeys(frameworks))

    return {"primary": primary, "secondaries": secondaries, "frameworks": frameworks}


def _collect_key_files(root: Path) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    # include explicit KEY_PATHS first
    for pat in KEY_PATHS:
        p = root / pat
        if pat.endswith("/") or p.is_dir():
            # include a few files from the directory
            if p.exists() and p.is_dir():
                count = 0
                for f in p.glob("**/*"):
                    if f.is_file() and not _is_binary(f):
                        rel = f.relative_to(root).as_posix()
                        # redact lockfiles just in case
                        if f.name in REDACT_LOCKFILE_NAMES:
                            out[rel] = {"path": rel, "content": _redacted_placeholder(f)}
                        else:
                            out[rel] = {"path": rel, "content": _read_text_capped(f)}
                        count += 1
                        if count >= 3:
                            break
            continue

        if p.exists() and p.is_file() and not _is_binary(p):
            rel = p.relative_to(root).as_posix()
            if p.name in REDACT_LOCKFILE_NAMES:
                out[rel] = {"path": rel, "content": _redacted_placeholder(p)}
            else:
                out[rel] = {"path": rel, "content": _read_text_capped(p)}
    # also look for common lockfiles at root and redact them (don’t include full content)
    for name in REDACT_LOCKFILE_NAMES:
        lf = root / name
        if lf.exists() and lf.is_file():
            rel = lf.relative_to(root).as_posix()
            out.setdefault(rel, {"path": rel, "content": _redacted_placeholder(lf)})
    return out


def _build_file_list(root: Path) -> List[Dict[str, Any]]:
    """
    Flat list of *text* files in the repo (skip binaries and ignored dirs).
    """
    files: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune directories
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for fn in filenames:
            p = Path(dirpath) / fn
            if _is_binary(p):
                continue
            rel = p.relative_to(root).as_posix()
            try:
                size = p.stat().st_size
            except Exception:
                size = None
            lang = LANG_EXT.get(p.suffix.lower())
            files.append({"path": rel, "type": "file", "size": size, "lang": lang})
    return files


def _sample_folder_files(root: Path) -> List[Dict[str, Any]]:
    """
    For each top-level folder, pick up to 2 small representative text files and
    include short excerpts to help later LLM prompts.
    """
    samples: List[Dict[str, Any]] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or _should_ignore_dir(entry.name):
            continue
        # find code files within this folder
        code_files = [
            p for p in entry.rglob("*")
            if p.is_file() and not _is_binary(p)
        ]
        # prioritize known language files
        prioritized = [p for p in code_files if p.suffix.lower() in LANG_EXT]
        candidates = prioritized or code_files
        # pick the 2 smallest text files (cheap to excerpt)
        candidates = sorted(candidates, key=lambda p: (p.stat().st_size if p.exists() else 0))[:2]
        if not candidates:
            continue
        samples.append({
            "path": entry.relative_to(root).as_posix(),
            "sample_files": [
                {
                    "path": f.relative_to(root).as_posix(),
                    "excerpt": _make_excerpt(f)
                }
                for f in candidates
            ]
        })
    return samples


# --------- Public API ---------
def scan_repo(root_path: str | Path) -> Dict[str, Any]:
    """
    Scan a repository folder and return a structured summary (dict).

    Returns a dict with:
      - root, ascii_tree, tree, ecosystem, key_files,
        folder_summaries, signals
    """
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

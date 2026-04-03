from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Iterable, Optional

# ---- Try to import the scorer (optional) ----
try:
    from score_repo_files import select_top_files_local
except Exception:
    select_top_files_local = None

# --------- Tunable knobs ---------
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".pnpm-store",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "out",
    ".cache",
    ".idea",
    ".vscode",
    ".terraform",
    "target",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
}

BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
}

# Files/paths we’ll try to read and include (truncated) as context
KEY_PATHS = [
    "README.md",
    "README",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "package.json",
    "tsconfig.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yaml",
    "Makefile",
    ".tool-versions",
    ".nvmrc",
    ".python-version",
    ".env.example",
    "devcontainer.json",
    "deno.json",
    "deno.jsonc",
    "turbo.json",
    "nx.json",
    "lerna.json",
    "pnpm-workspace.yaml",
    "ruff.toml",
    ".github/workflows",  # directory (handled specially)
]

REDACT_LOCKFILE_NAMES = {
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
}

MAX_KEY_FILE_BYTES = 60_000
EXCERPT_HEAD_LINES = 80
EXCERPT_TAIL_LINES = 20
ASCII_TREE_MAX_LINES = 600

LANG_EXT = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".c": "C",
    ".h": "C Header",
    ".cpp": "C++",
    ".hpp": "C++ Header",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".env": "Dotenv",
    ".md": "Markdown",
    ".vue": "Vue",
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
                [
                    e
                    for e in d.iterdir()
                    if not (e.is_dir() and _should_ignore_dir(e.name))
                ],
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except PermissionError:
            return
        for i, e in enumerate(entries):
            is_last = i == len(entries) - 1
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
            pkg = json.loads(
                (root / "package.json").read_text(encoding="utf-8", errors="ignore")
            )
            deps = {}
            deps.update(pkg.get("dependencies", {}) or {})
            deps.update(pkg.get("devDependencies", {}) or {})
            names = set(map(str.lower, deps.keys()))
            for dep, fw in [
                ("next", "nextjs"), ("nextjs", "nextjs"),
                ("react", "react"), ("preact", "react"),
                ("vite", "vite"),
                ("express", "express"),
                ("fastify", "fastify"),
                ("hono", "hono"),
                ("nuxt", "nuxt"),
                ("vue", "vue"),
                ("svelte", "svelte"), ("@sveltejs/kit", "svelte"),
                ("astro", "astro"),
                ("remix", "remix"), ("@remix-run/node", "remix"),
            ]:
                if dep in names and fw not in frameworks:
                    frameworks.append(fw)
        except Exception:
            pass

    if exists("deno.json") or exists("deno.jsonc"):
        if primary is None:
            primary = "deno"
        else:
            secondaries.append("deno")

    if exists("bun.lockb"):
        if primary is None:
            primary = "bun"
        else:
            secondaries.append("bun")

    if exists("pyproject.toml") or exists("requirements.txt") or exists("setup.py"):
        if primary is None:
            primary = "python"
        else:
            secondaries.append("python")
        _py_fw_map = {
            "django": "django", "flask": "flask", "fastapi": "fastapi",
            "starlette": "starlette", "tornado": "tornado",
            "aiohttp": "aiohttp", "litestar": "litestar",
        }
        for req_file in ["requirements.txt", "requirements-dev.txt", "pyproject.toml"]:
            rp = root / req_file
            if rp.exists():
                try:
                    content = rp.read_text(encoding="utf-8", errors="ignore").lower()
                    for pkg_name, fw_name in _py_fw_map.items():
                        if pkg_name in content and fw_name not in frameworks:
                            frameworks.append(fw_name)
                except Exception:
                    pass

    if exists("go.mod"):
        primary = primary or "go"
        if primary != "go":
            secondaries.append("go")

    if exists("Cargo.toml"):
        primary = primary or "rust"
        if primary != "rust":
            secondaries.append("rust")

    if exists("pom.xml"):
        primary = primary or "java"
        if primary != "java":
            secondaries.append("java")

    if exists("build.gradle") or exists("build.gradle.kts"):
        primary = primary or "java"
        if primary != "java":
            secondaries.append("java")
        if exists("build.gradle.kts") and "kotlin" not in frameworks:
            frameworks.append("kotlin")

    if any(root.glob("*.csproj")) or any(root.glob("*.sln")) or exists("global.json"):
        primary = primary or "dotnet"
        if primary != "dotnet":
            secondaries.append("dotnet")

    if exists("Gemfile"):
        primary = primary or "ruby"
        if primary != "ruby":
            secondaries.append("ruby")
        try:
            content = (root / "Gemfile").read_text(encoding="utf-8", errors="ignore").lower()
            if "rails" in content:
                frameworks.append("rails")
            elif "sinatra" in content:
                frameworks.append("sinatra")
        except Exception:
            pass

    if exists("composer.json"):
        primary = primary or "php"
        if primary != "php":
            secondaries.append("php")
        try:
            data = json.loads(
                (root / "composer.json").read_text(encoding="utf-8", errors="ignore")
            )
            all_deps = set(map(str.lower, (data.get("require", {}) or {}).keys()))
            if "laravel/framework" in all_deps:
                frameworks.append("laravel")
            elif "symfony/framework-bundle" in all_deps:
                frameworks.append("symfony")
        except Exception:
            pass

    if exists("Dockerfile") or exists("compose.yaml") or exists("docker-compose.yml"):
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
                            out[rel] = {
                                "path": rel,
                                "content": _redacted_placeholder(f),
                            }
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
    samples: List[Dict[str, Any]] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or _should_ignore_dir(entry.name):
            continue
        code_files = [p for p in entry.rglob("*") if p.is_file() and not _is_binary(p)]
        prioritized = [p for p in code_files if p.suffix.lower() in LANG_EXT]
        candidates = prioritized or code_files
        candidates = sorted(
            candidates, key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True
        )[:2]
        if not candidates:
            continue
        samples.append(
            {
                "path": entry.relative_to(root).as_posix(),
                "sample_files": [
                    {
                        "path": f.relative_to(root).as_posix(),
                        "excerpt": _make_excerpt(f),
                    }
                    for f in candidates
                ],
            }
        )
    return samples


def _detect_test_framework(root: Path, files: List[Dict[str, Any]]) -> Optional[str]:
    if (root / "pytest.ini").exists() or (root / "conftest.py").exists():
        return "pytest"
    if exists_under := (root / "pyproject.toml"):
        try:
            content = exists_under.read_text(encoding="utf-8", errors="ignore")
            if "[tool.pytest" in content:
                return "pytest"
        except Exception:
            pass
    if (root / "package.json").exists():
        try:
            pkg = json.loads(
                (root / "package.json").read_text(encoding="utf-8", errors="ignore")
            )
            deps = {}
            deps.update(pkg.get("dependencies", {}) or {})
            deps.update(pkg.get("devDependencies", {}) or {})
            names = set(map(str.lower, deps.keys()))
            if "vitest" in names:
                return "vitest"
            if "jest" in names or "@jest/core" in names:
                return "jest"
            if "mocha" in names:
                return "mocha"
            if "jasmine" in names:
                return "jasmine"
        except Exception:
            pass
    if (root / "Gemfile").exists():
        try:
            content = (root / "Gemfile").read_text(encoding="utf-8", errors="ignore").lower()
            if "rspec" in content:
                return "rspec"
            if "minitest" in content:
                return "minitest"
        except Exception:
            pass
    if (root / "Cargo.toml").exists():
        return "cargo-test"
    if (root / "go.mod").exists():
        return "go-test"
    return None


# --------- Public: scan summary ---------
def scan_repo(
    root_path: str | Path, top_n_important: Optional[int] = None
) -> Dict[str, Any]:
    root = Path(root_path).resolve()
    files = _build_file_list(root)
    signals = {
        "has_tests": any(
            Path(f["path"]).parts[0].lower() in ("test", "tests", "spec", "__tests__", "specs")
            for f in files
        ),
        "has_ci": (root / ".github" / "workflows").exists()
            or (root / ".circleci").exists()
            or (root / ".gitlab-ci.yml").exists(),
        "has_containerization": (root / "Dockerfile").exists()
            or (root / "docker-compose.yml").exists()
            or (root / "compose.yaml").exists(),
        "has_migrations": any("migrations" in Path(f["path"]).parts for f in files),
        "has_linting": any(
            (root / p).exists()
            for p in [
                ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
                ".eslintrc.yaml", ".eslintrc.yml",
                ".flake8", "ruff.toml", ".ruff.toml", "pylintrc", ".pylintrc",
                ".stylelintrc", ".stylelintrc.json",
            ]
        ),
        "test_framework": _detect_test_framework(root, files),
        "has_monorepo": any(
            (root / p).exists()
            for p in ["pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json", "rush.json"]
        ),
    }
    result: Dict[str, Any] = {
        "root": root.as_posix(),
        "ascii_tree": _ascii_tree(root),
        "tree": files,
        "ecosystem": _detect_ecosystem(root),
        "key_files": _collect_key_files(root),
        "folder_summaries": _sample_folder_files(root),
        "signals": signals,
    }

    # ---- Optional important_files scoring ----
    if top_n_important and select_top_files_local:
        try:
            top = select_top_files_local(str(root), top_n=top_n_important)
            result["important_files"] = [rel for (rel, _) in top]
        except Exception as e:
            result["important_files_error"] = f"{type(e).__name__}: {e}"
    elif top_n_important and not select_top_files_local:
        result["important_files_error"] = (
            "Scorer not available (score_repo_files.py not importable)."
        )

    return result


# --------- Dependency graph extraction ----------
_JS_TS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"}
_PY_EXTS = {".py"}
_JS_TS_INDEX_CANDIDATES = [
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "index.mjs",
    "index.cjs",
    "index.vue",
]
_JS_TS_FILE_EXTS_TRY = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".json"]
_PY_FILE_EXTS_TRY = [".py", "/__init__.py"]

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
    re.MULTILINE,
)

_GO_EXTS = {".go"}
_RUST_EXTS = {".rs"}

RE_GO_IMPORT_BLOCK = re.compile(r'import\s*\(\s*(.*?)\s*\)', re.DOTALL)
RE_GO_IMPORT_LINE = re.compile(r'(?:[\w.]+\s+)?"([^"]+)"')
RE_GO_IMPORT_SINGLE = re.compile(r'^import\s+(?:[\w.]+\s+)?"([^"]+)"', re.MULTILINE)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _vue_script_block(text: str) -> str:
    m = re.findall(
        r"<script[^>]*>(.*?)</script>", text, flags=re.DOTALL | re.IGNORECASE
    )
    return "\n\n".join(m) if m else text


def _resolve_js_like(spec: str, src_file: Path, root: Path) -> Optional[Path]:
    if not spec.startswith("."):
        return None
    base = (src_file.parent / spec).resolve()
    if base.suffix and base.exists():
        return base
    for ext in _JS_TS_FILE_EXTS_TRY:
        cand = Path(str(base) + ext)
        if cand.exists():
            return cand
    if base.exists() and base.is_dir():
        for name in _JS_TS_INDEX_CANDIDATES:
            cand = base / name
            if cand.exists():
                return cand
    return None


def _resolve_js_alias(spec: str, root: Path, aliases: Dict[str, str]) -> Optional[Path]:
    for prefix, replacement in aliases.items():
        if not prefix or not spec.startswith(prefix):
            continue
        remainder = spec[len(prefix):]
        base = (root / replacement / remainder).resolve()
        if base.suffix and base.exists():
            return base
        for ext in _JS_TS_FILE_EXTS_TRY:
            cand = Path(str(base) + ext)
            if cand.exists():
                return cand
        if base.exists() and base.is_dir():
            for name in _JS_TS_INDEX_CANDIDATES:
                cand = base / name
                if cand.exists():
                    return cand
    return None


def _resolve_py_like(module: str, src_file: Path, root: Path) -> Optional[Path]:
    if not module.startswith("."):
        return None
    dots = len(module) - len(module.lstrip("."))
    remainder = module[dots:]
    target_dir = src_file.parent
    for _ in range(dots - 1):
        target_dir = target_dir.parent
    if remainder:
        parts = remainder.split(".")
        target_dir = target_dir.joinpath(*parts)
    for suffix in _PY_FILE_EXTS_TRY:
        cand = Path(str(target_dir) + suffix)
        if cand.exists():
            return cand
    return None


def _parse_go_module(root: Path) -> Optional[str]:
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return None
    for line in go_mod.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("module "):
            parts = line.strip().split()
            return parts[1] if len(parts) >= 2 else None
    return None


def _resolve_go_like(spec: str, root: Path, module_name: str) -> Optional[Path]:
    if not spec.startswith(module_name + "/"):
        return None
    rel = spec[len(module_name) + 1:]
    if not rel:
        return None
    pkg_dir = root / rel
    if pkg_dir.exists() and pkg_dir.is_dir():
        for f in sorted(pkg_dir.glob("*.go")):
            if not f.name.endswith("_test.go"):
                return f
    return None


def _find_rust_src_root(root: Path) -> Path:
    src = root / "src"
    return src if src.exists() else root


def _resolve_rust_like(
    anchor: str, mod_path: str, src_file: Path, rust_src: Path
) -> Optional[Path]:
    parts = []
    for p in mod_path.split("::"):
        p = p.strip()
        if not p or not re.match(r"^[a-z_][a-z0-9_]*$", p):
            break
        parts.append(p)
    if not parts:
        return None
    base = rust_src if anchor == "crate" else src_file.parent
    target = base.joinpath(*parts)
    if target.with_suffix(".rs").exists():
        return target.with_suffix(".rs")
    if (target / "mod.rs").exists():
        return target / "mod.rs"
    return None


def _load_ts_path_aliases(root: Path) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for name in ["tsconfig.json", "tsconfig.base.json", "tsconfig.app.json"]:
        cfg = root / name
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8", errors="ignore"))
            paths = data.get("compilerOptions", {}).get("paths", {})
            for alias_pat, targets in paths.items():
                if not targets:
                    continue
                alias_key = alias_pat.rstrip("*")
                target_val = targets[0].rstrip("*")
                aliases[alias_key] = target_val
        except Exception:
            pass
        break
    return aliases


def _extract_imports_for_file(
    fpath: Path,
    root: Path,
    *,
    go_module: Optional[str] = None,
    rust_src: Optional[Path] = None,
    ts_aliases: Optional[Dict[str, str]] = None,
):
    text = _read_text(fpath)
    suffix = fpath.suffix.lower()
    if suffix == ".vue":
        text = _vue_script_block(text)

    if suffix in _JS_TS_EXTS:
        for m in RE_JS_IMPORTS.finditer(text):
            spec = (
                m.group("imp1")
                or m.group("imp2")
                or m.group("imp3")
                or m.group("imp4")
                or m.group("imp5")
            )
            if not spec:
                continue
            tgt = _resolve_js_like(spec, fpath, root)
            if not tgt and ts_aliases and not spec.startswith("."):
                tgt = _resolve_js_alias(spec, root, ts_aliases)
            if not tgt:
                continue
            try:
                yield tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue

    elif suffix in _PY_EXTS:
        for m in RE_PY_IMPORTS.finditer(text):
            spec = m.group("from") or m.group("imp")
            if not spec:
                continue
            tgt = _resolve_py_like(spec, fpath, root)
            if not tgt:
                continue
            try:
                yield tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue

    elif suffix in _GO_EXTS and go_module:
        cleaned = RE_GO_IMPORT_BLOCK.sub("__BLOCK__", text)
        for block_m in RE_GO_IMPORT_BLOCK.finditer(text):
            for line_m in RE_GO_IMPORT_LINE.finditer(block_m.group(1)):
                spec = line_m.group(1)
                tgt = _resolve_go_like(spec, root, go_module)
                if not tgt:
                    continue
                try:
                    yield tgt.resolve().relative_to(root.resolve())
                except Exception:
                    continue
        for m in RE_GO_IMPORT_SINGLE.finditer(cleaned):
            spec = m.group(1)
            tgt = _resolve_go_like(spec, root, go_module)
            if not tgt:
                continue
            try:
                yield tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue

    elif suffix in _RUST_EXTS and rust_src:
        for m in re.finditer(
            r"^\s*use\s+(crate|super)::([^;{\s\\*]+)", text, re.MULTILINE
        ):
            tgt = _resolve_rust_like(m.group(1), m.group(2), fpath, rust_src)
            if not tgt:
                continue
            try:
                yield tgt.resolve().relative_to(root.resolve())
            except Exception:
                continue
        for block_m in re.finditer(
            r"^\s*use\s+(crate|super)::\{([^}]+)\}", text, re.MULTILINE
        ):
            anchor = block_m.group(1)
            for item in block_m.group(2).split(","):
                item = item.strip()
                tgt = _resolve_rust_like(anchor, item, fpath, rust_src)
                if not tgt:
                    continue
                try:
                    yield tgt.resolve().relative_to(root.resolve())
                except Exception:
                    continue


def build_dependency_graph(root_path: str | Path) -> Dict[str, Any]:
    """
    Return {"nodes":[{"id": "...", "label": "..."}], "edges":[{"source":"...","target":"..."}]}
    Supports relative imports in JS/TS/Vue, Python, Go (module-relative), and Rust (crate-relative).
    """
    root = Path(root_path).resolve()

    go_module = _parse_go_module(root)
    rust_src = _find_rust_src_root(root) if (root / "Cargo.toml").exists() else None
    ts_aliases = _load_ts_path_aliases(root)

    _ALL_SRC_EXTS = _JS_TS_EXTS | _PY_EXTS | _GO_EXTS | _RUST_EXTS

    src_files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for fn in filenames:
            p = Path(dirpath) / fn
            if _is_binary(p):
                continue
            if p.suffix.lower() in _ALL_SRC_EXTS:
                src_files.append(p)

    node_ids: Dict[str, Dict[str, str]] = {}
    edges: List[Dict[str, str]] = []

    def _add_node(rel: Path):
        rid = rel.as_posix()
        if rid not in node_ids:
            node_ids[rid] = {"id": rid, "label": rel.name}

    for f in src_files:
        rel = f.relative_to(root)
        _add_node(rel)

    for f in src_files:
        src_rel = f.relative_to(root)
        for tgt_rel in _extract_imports_for_file(
            f, root,
            go_module=go_module,
            rust_src=rust_src,
            ts_aliases=ts_aliases,
        ):
            _add_node(tgt_rel)
            edges.append({"source": src_rel.as_posix(), "target": tgt_rel.as_posix()})

    nodes = list(node_ids.values())
    return {"nodes": nodes, "edges": edges}

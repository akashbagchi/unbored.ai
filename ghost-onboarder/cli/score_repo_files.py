#!/usr/bin/env python3
"""
Score repo files by importance and return the top-N.

Scoring formula:
  score =
      + 4 * is_entrypoint
      + 3 * runtime_signal          # server/api/db/auth/queue/env usage
      + 2 * imported_by_count
      + 1 * churn_weight            # capped/log-scaled
      - 3 * is_tooling_config       # eslint/tailwind/postcss/prettier/jest/etc.
      - 2 * is_test_or_fixture
      - 1 * is_types_only

- Works for Python + JS/TS projects (import heuristics included).
- Uses `git` CLI for churn; requires Git on PATH.

CLI examples:
  python score_repo_files.py --repo https://github.com/tiangolo/fastapi.git --top-n 15
  python score_repo_files.py --repo <url> --top-n 10 --max-commits 300 --exts .py,.ts
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------- Tunables ----------------
DEFAULT_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx"}
IGNORE_DIRS = {".git", "node_modules", ".venv", "dist", "build", "__pycache__", ".mypy_cache", ".tox", ".idea"}
MAX_FILE_BYTES = 400_000
DEFAULT_MAX_COMMITS = 200

ENTRYPOINT_NAMES = {"main", "app", "server", "cli", "manage", "index", "wsgi", "asgi"}

RUNTIME_PATH_HINTS = (
    "server/", "api/", "routes/", "router/", "controllers/", "controller/",
    "services/", "service/", "db/", "database/", "models/", "entities/",
    "auth/", "workers/", "jobs/"
)

TOOLING_BASENAMES = {
    "eslint.config.js","eslint.config.cjs",".eslintrc.js",".eslintrc.cjs",".eslintrc.ts",".eslintrc.json",
    "tailwind.config.js","tailwind.config.cjs","postcss.config.js","postcss.config.cjs",
    "lint-staged.config.js","lint-staged.config.cjs",
    "prettier.config.js",".prettierrc",".prettierrc.json",".prettierrc.js",
    "vitest.config.ts","vitest.config.js","jest.config.js","jest.config.ts","tsconfig.json"
}

TYPES_ONLY_SUFFIXES = {".d.ts"}

# Weights
W_ENTRYPOINT = 4
W_RUNTIME = 3
W_IMPORTED_BY = 2
W_CHURN = 1
W_TOOLING_PENALTY = -3
W_TEST_PENALTY = -2
W_TYPES_PENALTY = -1
CHURN_CAP = 5  # cap raw churn contribution
# ------------------------------------------


def run(cmd: List[str], cwd: str | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout


def shallow_clone(repo_url: str, workdir: str) -> str:
    repo_dir = os.path.join(workdir, "repo")
    run(["git", "clone", "--depth", "1", repo_url, repo_dir])
    return repo_dir


def iter_source_files(root: str, exts=DEFAULT_EXTS) -> List[Path]:
    files = []
    r = Path(root)
    for p in r.rglob("*"):
        if p.is_dir():
            rel = p.relative_to(r)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
        if p.is_file() and p.suffix.lower() in exts:
            rel = p.relative_to(r)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            if p.stat().st_size <= MAX_FILE_BYTES:
                files.append(p)
    return files


def read_text_safely(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def detect_entrypoint(path: Path, content: str) -> int:
    """
    Entrypoint detection:
      - filename starts with/equals typical entry names
      - Python: __main__ guard, app.run, CLI hints (Typer/Click), uvicorn/FastAPI
      - JS/TS: express/koa/fastify/createServer/app.listen
    """
    name = path.stem.lower()
    if any(name.startswith(n) or name == n for n in ENTRYPOINT_NAMES):
        return 1

    if path.suffix == ".py":
        if re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', content): return 1
        if re.search(r'\bapp\.run\(', content): return 1
        if "entry_points" in content or "console_scripts" in content: return 1
        if re.search(r'\b(Flask|FastAPI|Typer|Click|uvicorn)\b', content): return 1

    if path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
        if re.search(r'(express|koa|fastify|createServer|app\.listen)', content): return 1

    return 0


# -------- Import graph heuristics --------
PY_IMPORT_RE = re.compile(r'^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.,\s]+))', re.MULTILINE)
JS_IMPORT_RE = re.compile(r'^\s*import\s+(?:.+?\s+from\s+)?[\'"]([^\'"]+)[\'"]', re.MULTILINE)
JS_REQUIRE_RE = re.compile(r'^\s*const\s+\w+\s*=\s*require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)

def build_import_graph(files: List[Path], repo_root: str) -> Dict[str, int]:
    from collections import Counter, defaultdict

    imported_by = Counter()
    file_key_by_relpath = {}
    for p in files:
        key = p.stem
        rel = str(p.relative_to(repo_root)).replace("\\", "/")
        file_key_by_relpath[rel] = key

    paths_by_key = defaultdict(set)
    for rel, key in file_key_by_relpath.items():
        paths_by_key[key].add(rel)

    for p in files:
        content = read_text_safely(p)
        imported_keys = set()
        if p.suffix == ".py":
            for m in PY_IMPORT_RE.finditer(content):
                mod = (m.group(1) or m.group(2) or "").strip()
                if not mod:
                    continue
                mods = [part.strip() for part in mod.split(",")]
                for mm in mods:
                    stem = mm.split(".")[0]
                    if stem:
                        imported_keys.add(stem)
        elif p.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            for m in JS_IMPORT_RE.finditer(content):
                spec = m.group(1)
                if spec.startswith("."):
                    stem = os.path.basename(spec).split(".")[0]
                    if stem:
                        imported_keys.add(stem)
            for m in JS_REQUIRE_RE.finditer(content):
                spec = m.group(1)
                if spec.startswith("."):
                    stem = os.path.basename(spec).split(".")[0]
                    if stem:
                        imported_keys.add(stem)

        for key in imported_keys:
            if key in paths_by_key:
                imported_by[key] += 1

    imported_by_count = {rel: imported_by[file_key_by_relpath[rel]] for rel in file_key_by_relpath}
    return imported_by_count


# -------- Churn (recent commits touching) --------
def compute_churn(repo_dir: str, max_commits: int) -> Counter:
    out = run(["git", "log", "--pretty=format:", "--name-only", "-n", str(max_commits)], cwd=repo_dir)
    paths = [line.strip() for line in out.splitlines() if line.strip()]
    norm = [p.replace("\\", "/") for p in paths if not p.endswith("/")]
    return Counter(norm)


# -------- Extra signals / penalties --------
ENV_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")

def is_tooling_config(path: str) -> int:
    base = path.split("/")[-1]
    return 1 if base in TOOLING_BASENAMES else 0

def is_test_or_fixture(path: str) -> int:
    p = path.lower()
    return 1 if any(seg in p for seg in ("/test/", "/tests/", "/__tests__", "/fixtures/", ".spec.", ".test.")) else 0

def is_types_only(path: str) -> int:
    return 1 if any(path.endswith(s) for s in TYPES_ONLY_SUFFIXES) else 0

def runtime_signal(path: str, content: str) -> int:
    """
    Return 0/1/2 based on 'runtime-critical' features:
      + path hints (server/api/db/controllers/services/auth)
      + DB/ORM/framework/auth cues
      + ENV usage (process.env/getenv/dotenv)
    """
    score = 0
    if any(h in path.lower() for h in RUNTIME_PATH_HINTS):
        score += 1
    if re.search(r"\b(prisma|drizzle|typeorm|sequelize|mongoose|knex|sqlalchemy|postgres|redis|kafka|rabbitmq)\b", content, re.I):
        score += 1
    if re.search(r"\b(router|controller|service|middleware|worker|queue|job)\b", content, re.I):
        score += 1
    if ENV_PATTERN.search(content) and re.search(r"(process\.env|Deno\.env|getenv|dotenv)", content, re.I):
        score += 1
    return min(score, 2)

def churn_weight(raw: int) -> int:
    return min(raw, CHURN_CAP)


def score_files(repo_dir: str, top_n: int, max_commits: int, exts=DEFAULT_EXTS) -> List[Tuple[str, dict]]:
    root = Path(repo_dir)
    files = iter_source_files(repo_dir, exts=exts)
    if not files:
        return []

    imported_by_count = build_import_graph(files, repo_dir)
    churn = compute_churn(repo_dir, max_commits)

    scored: List[Tuple[str, dict]] = []
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        content = read_text_safely(p)

        is_entry = detect_entrypoint(p, content)
        imported_by = imported_by_count.get(rel, 0)
        recent_touches = churn.get(rel, 0)
        tooling = is_tooling_config(rel)
        tests = is_test_or_fixture(rel)
        types = is_types_only(rel)
        runtime = runtime_signal(rel, content)
        churn_w = churn_weight(recent_touches)

        score = (
            W_ENTRYPOINT * is_entry +
            W_RUNTIME * runtime +
            W_IMPORTED_BY * imported_by +
            W_CHURN * churn_w +
            W_TOOLING_PENALTY * tooling +
            W_TEST_PENALTY * tests +
            W_TYPES_PENALTY * types
        )

        scored.append((rel, {
            "score": int(score),
            "weights": {
                "entrypoint": W_ENTRYPOINT,
                "runtime": W_RUNTIME,
                "imported_by": W_IMPORTED_BY,
                "churn": W_CHURN,
                "tooling_penalty": W_TOOLING_PENALTY,
                "test_penalty": W_TEST_PENALTY,
                "types_penalty": W_TYPES_PENALTY
            },
            "components": {
                "is_entrypoint": is_entry,
                "runtime_signal": runtime,
                "imported_by_count": imported_by,
                "recent_commits_touching": recent_touches,
                "tooling_config": tooling,
                "is_test_or_fixture": tests,
                "is_types_only": types
            },
            "bytes": p.stat().st_size
        }))

    # Fallback: ensure at least one entrypoint-like file
    if not any(m["components"]["is_entrypoint"] == 1 for _, m in scored):
        rel_central = None
        if imported_by_count:
            rel_central = max(imported_by_count.items(), key=lambda kv: kv[1])[0]
        if rel_central:
            for i, (rel, meta) in enumerate(scored):
                if rel == rel_central:
                    meta["components"]["is_entrypoint"] = 1
                    meta["score"] += W_ENTRYPOINT
                    scored[i] = (rel, meta)
                    break

    scored.sort(
        key=lambda kv: (
            kv[1]["score"],
            kv[1]["components"]["runtime_signal"],
            kv[1]["components"]["imported_by_count"],
            -kv[1]["bytes"]
        ),
        reverse=True
    )
    return scored[:top_n]


# ---------------- CLI & public helpers ----------------

def select_top_files_local(repo_dir: str, top_n: int = 30, max_commits: int = DEFAULT_MAX_COMMITS, exts=None):
    """
    Score files in an already-cloned local repo and return top-N.
    Returns: List[Tuple[path, meta_dict]] same as score_files().
    """
    exts = exts or DEFAULT_EXTS
    return score_files(repo_dir, top_n=top_n, max_commits=DEFAULT_MAX_COMMITS if max_commits is None else max_commits, exts=exts)


def main():
    ap = argparse.ArgumentParser(description="Score important files in a Git repo and print the top N.")
    ap.add_argument("--repo", required=True, help="Git URL, e.g., https://github.com/nvbn/thefuck.git")
    ap.add_argument("--top-n", type=int, default=10, help="How many files to return (default: 10)")
    ap.add_argument("--max-commits", type=int, default=DEFAULT_MAX_COMMITS, help="Commits to scan for churn")
    ap.add_argument("--exts", default=",".join(sorted(DEFAULT_EXTS)),
                    help="Comma-separated extensions (default: .js,.jsx,.py,.ts,.tsx)")
    args = ap.parse_args()

    exts = {e if e.startswith(".") else f".{e}" for e in args.exts.split(",")}

    workdir = tempfile.mkdtemp(prefix="score_repo_")
    try:
        print(f"Cloning into temp dir: {workdir}")
        repo_dir = shallow_clone(args.repo, workdir)
        top = score_files(repo_dir, top_n=args.top_n, max_commits=args.max_commits, exts=exts)

        # Pretty
        print("\nTop files by importance:\n")
        for i, (rel, meta) in enumerate(top, 1):
            c = meta["components"]
            print(f"{i:2}. {rel}")
            print(f"    score = {meta['score']}  "
                  f"(4*{c['is_entrypoint']}  + 3*{c['runtime_signal']}  "
                  f"+ 2*{c['imported_by_count']}  + 1*{min(c['recent_commits_touching'], CHURN_CAP)}  "
                  f"-3*{c['tooling_config']}  -2*{c['is_test_or_fixture']}  -1*{c['is_types_only']})")
            print(f"    size  = {meta['bytes']} bytes")

        # JSON (easy to pipe)
        print("\nRaw JSON:")
        print(json.dumps([{ "path": rel, **meta } for rel, meta in top], indent=2))

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    if shutil.which("git") is None:
        print("Error: 'git' not found on PATH. Please install Git.", file=sys.stderr)
        raise SystemExit(1)
    main()

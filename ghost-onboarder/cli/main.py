from __future__ import annotations
import json
from pathlib import Path
import sys
import typer
from typing import Iterable, Dict, Any, List, Optional

from cli.scanner import scan_repo, build_dependency_graph
from cli.github_client import GitHubClient, keyword_filter

app = typer.Typer(add_completion=False)

# ---------- Human-readable summary ----------
def _summarize_human(data: dict) -> str:
    from textwrap import indent
    root = data.get("root", "")
    eco = data.get("ecosystem", {}) or {}
    sig = data.get("signals", {}) or {}
    tree_lines = (data.get("ascii_tree", "") or "").splitlines()
    tree_preview = "\n".join(tree_lines[:40] + (["... (truncated)"] if len(tree_lines) > 40 else []))

    key_files = data.get("key_files", {}) or {}
    def preview(txt: str, limit: int = 300) -> str:
        if not txt: return ""
        if len(txt) <= limit: return txt
        return txt[:limit] + "\n... (truncated)"

    key_list = []
    for k in sorted(key_files.keys()):
        content = key_files[k].get("content", "")
        key_list.append(f"- {k}\n{indent(preview(content), '  ')}")

    fsum = data.get("folder_summaries", []) or []
    folder_lines = []
    for f in fsum[:10]:
        folder_lines.append(f"• {f.get('path')}")
        for sf in (f.get("sample_files") or [])[:2]:
            folder_lines.append(f"    - {sf.get('path')} (excerpt)")
    if len(fsum) > 10:
        folder_lines.append("• ... (more folders truncated)")

    parts = [
        f"# Scan Summary: {root}",
        "",
        "## Ecosystem",
        f"- primary: {eco.get('primary')}",
        f"- frameworks: {', '.join(eco.get('frameworks') or []) or '—'}",
        f"- secondaries: {', '.join(eco.get('secondaries') or []) or '—'}",
        "",
        "## Signals",
        f"- has_tests: {sig.get('has_tests')}",
        f"- has_ci: {sig.get('has_ci')}",
        f"- has_containerization: {sig.get('has_containerization')}",
        f"- has_migrations: {sig.get('has_migrations')}",
        "",
        "## Repo Tree (preview)",
        "```",
        tree_preview,
        "```",
        "",
        "## Key Files (short previews)",
        "\n".join(key_list[:8]) or "—",
        "" if len(key_list) <= 8 else "\n... (more key files truncated)\n",
        "## Folder Samples",
        "\n".join(folder_lines) or "—",
        "",
        "Tip: Use --format json | jsonl for machine-readable output. Use --graph-out to write a dependency graph.",
    ]
    return "\n".join(parts)

# ---------- JSONL helpers ----------
def _iter_jsonl_records(data: Dict[str, Any], include: Iterable[str]) -> Iterable[Dict[str, Any]]:
    include = set(include)
    if "meta" in include:
        yield {"section": "meta", "root": data.get("root")}
    if "ascii_tree" in include:
        yield {"section": "ascii_tree", "value": data.get("ascii_tree")}
    if "ecosystem" in include:
        yield {"section": "ecosystem", **(data.get("ecosystem") or {})}
    if "signals" in include:
        yield {"section": "signals", **(data.get("signals") or {})}
    if "key_files" in include:
        key_files = data.get("key_files") or {}
        for path, obj in key_files.items():
            yield {"section": "key_files", "path": path, "content": (obj or {}).get("content", "")}
    if "folder_summaries" in include:
        for folder in (data.get("folder_summaries") or []):
            yield {"section": "folder_summaries", "path": folder.get("path"), "sample_files": folder.get("sample_files") or []}
    if "tree" in include:
        for entry in (data.get("tree") or []):
            rec = {"section": "tree"}
            rec.update(entry or {})
            yield rec

def _write_jsonl(data: Dict[str, Any], out_path: Path | None, include: Iterable[str]) -> None:
    stream = sys.stdout if out_path is None else out_path.open("w", encoding="utf-8", newline="\n")
    try:
        for rec in _iter_jsonl_records(data, include):
            stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        if stream is not sys.stdout:
            stream.close()

def _write_json_or_jsonl(records: List[Dict[str, Any]], fmt: str, out_path: Optional[Path]) -> None:
    fmt = fmt.lower()
    if fmt == "jsonl":
        stream = sys.stdout if out_path is None else out_path.open("w", encoding="utf-8", newline="\n")
        try:
            for r in records:
                stream.write(json.dumps(r, ensure_ascii=False) + "\n")
        finally:
            if stream is not sys.stdout:
                stream.close()
    else:
        text = json.dumps(records, indent=2, ensure_ascii=False)
        if out_path:
            out_path.write_text(text, encoding="utf-8")
        else:
            typer.echo(text)

# ---------- CLI ----------
@app.command()
def scan(
    # Scanner
    repo: Path = typer.Option(..., "--repo", dir_okay=True, file_okay=False, help="Path to the repository"),
    out: Path = typer.Option(None, "--out", help="Scanner output file (stdout if omitted)"),
    format: str = typer.Option("human", "--format", "-f", help="Scanner format: human | json | jsonl"),
    include: list[str] = typer.Option(
        ["meta","ascii_tree","ecosystem","signals","key_files","folder_summaries","tree"],
        "--include",
        help="Scanner jsonl sections to include (repeat flag)."
    ),
    graph_out: Path = typer.Option(None, "--graph-out", help="Path to dependency graph JSON. If omitted & --out set, writes alongside"),
    # GitHub issues
    gh_repo: Optional[str] = typer.Option(
        None, "--gh-repo",
        help="GitHub repo in 'owner/name' form (e.g., akashbagchi/modern-portfolio). Enables closed-issues fetch."
    ),
    gh_token: Optional[str] = typer.Option(
        None, "--gh-token",
        help="GitHub token (or set env GITHUB_TOKEN). Needed for private repos / higher rate limit."
    ),
    issues_limit: int = typer.Option(
        0, "--issues-limit",
        help="How many CLOSED issues to fetch (skip PRs). 0 to skip fetching."
    ),
    issues_out: Optional[Path] = typer.Option(
        None, "--issues-out",
        help="Where to write issues output. If omitted but --out set, derives a sibling path (e.g., scan.json -> scan.issues.jsonl)."
    ),
    issues_format: str = typer.Option(
        "jsonl", "--issues-format",
        help="Issues output format: json | jsonl (default jsonl)."
    ),
    issues_keywords: List[str] = typer.Option(
        ["setup","install","installation","config","configuration","env","dotenv","build","run","local","error","windows","mac","linux","docker","pnpm","yarn","npm","node","python","requirements","virtualenv","vite","nuxt","next","tailwind","eslint"],
        "--issues-keyword",
        help="Repeat for multiple keywords. Leave empty to disable filtering."
    ),
    issues_min_hits: int = typer.Option(
        1, "--issues-min-hits",
        help="Minimum keyword hits to include an issue when filtering. Use 1..N. Use 0 to include all."
    ),
):
    """
    Run repository scan, write dependency graph, and (optionally) fetch closed GitHub issues.
    """
    # ----- SCANNER -----
    data = scan_repo(str(repo))

    fmt = format.lower()
    if fmt == "jsonl":
        _write_jsonl(data, out, include)
        if out:
            typer.echo(f"Wrote {out}")
    else:
        # Generate main file (human or json)
        text = json.dumps(data, indent=2, ensure_ascii=False) if fmt == "json" else _summarize_human(data)
        if out:
            out.write_text(text, encoding="utf-8")
            typer.echo(f"Wrote {out}")
        else:
            typer.echo(text)

        # If human format, also create a JSONL sidecar file for later steps
        if fmt == "human" and out:
            jsonl_path = out.with_suffix(out.suffix + ".jsonl")
            _write_jsonl(data, jsonl_path, include)
            typer.echo(f"Wrote {jsonl_path}")


    # ----- GRAPH -----
    graph = build_dependency_graph(str(repo))
    if graph_out is not None:
        gpath = graph_out
    elif out is not None:
        gpath = out.with_suffix(out.suffix + ".graph.json") if out.suffix else out.with_suffix(".graph.json")
    else:
        gpath = Path("scan.graph.json")
    gpath.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"Wrote {gpath}")

    # ----- GITHUB ISSUES (optional) -----
    if gh_repo and issues_limit > 0:
        client = GitHubClient(token=gh_token)
        raw = client.fetch_closed_issues(repo_full_name=gh_repo, limit=issues_limit, include_body=True)

        # Filter by keywords (set issues_min_hits=0 to keep all)
        filtered = keyword_filter(raw, issues_keywords, min_hits=max(0, issues_min_hits))

        # Decide output path
        if issues_out is not None:
            ipath = issues_out
        elif out is not None:
            # derive from --out
            base = out.with_suffix(out.suffix + ".issues") if out.suffix else out.with_suffix(".issues")
            ipath = base.with_suffix(base.suffix + (".jsonl" if issues_format.lower()=="jsonl" else ".json"))
        else:
            ipath = Path("issues.jsonl" if issues_format.lower()=="jsonl" else "issues.json")

        _write_json_or_jsonl(filtered, issues_format, ipath)
        typer.echo(f"Wrote {ipath}")

if __name__ == "__main__":
    app()

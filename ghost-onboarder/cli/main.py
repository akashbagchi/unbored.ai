from __future__ import annotations
import json
from pathlib import Path
import sys
import argparse
from typing import Iterable, Dict, Any
from scanner import scan_repo, build_dependency_graph

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
        if not txt:
            return ""
        if len(txt) <= limit:
            return txt
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
        "Tip: Use --format json or --format jsonl for machine-readable output.",
    ]
    return "\n".join(parts)

# ---------- JSONL helpers ----------
def _iter_jsonl_records(data: Dict[str, Any], include: Iterable[str]) -> Iterable[Dict[str, Any]]:
    """
    Yield NDJSON records. Each record carries a 'section' key.
    include: subset of {"meta","ascii_tree","ecosystem","signals","key_files","folder_summaries","tree","important_files"}
    """
    include = set(include)

    # meta (root path)
    if "meta" in include:
        yield {"section": "meta", "root": data.get("root")}

    # ascii_tree
    if "ascii_tree" in include:
        yield {"section": "ascii_tree", "value": data.get("ascii_tree")}

    # ecosystem
    if "ecosystem" in include:
        yield {"section": "ecosystem", **(data.get("ecosystem") or {})}

    # signals
    if "signals" in include:
        yield {"section": "signals", **(data.get("signals") or {})}

    # key_files: one line per file (path + content)
    if "key_files" in include:
        key_files = data.get("key_files") or {}
        for path, obj in key_files.items():
            yield {
                "section": "key_files",
                "path": path,
                "content": (obj or {}).get("content", "")
            }

    # folder_summaries: one line per folder, with a minimal structure
    if "folder_summaries" in include:
        for folder in (data.get("folder_summaries") or []):
            yield {
                "section": "folder_summaries",
                "path": folder.get("path"),
                "sample_files": folder.get("sample_files") or []
            }

    # tree: one line per file entry
    if "tree" in include:
        for entry in (data.get("tree") or []):
            rec = {"section": "tree"}
            rec.update(entry or {})
            yield rec

    # important_files (NEW)
    if "important_files" in include:
        for item in (data.get("important_files") or []):
            yield {"section": "important_files", "path": item}

def _write_jsonl(data: Dict[str, Any], out_path: Path | None, include: Iterable[str]) -> None:
    stream = sys.stdout if out_path is None else out_path.open("w", encoding="utf-8", newline="\n")
    try:
        for rec in _iter_jsonl_records(data, include):
            stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        if stream is not sys.stdout:
            stream.close()

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Run repository scan and optionally emit a dependency graph")
    parser.add_argument("--repo", required=True, help="Path to the repository")
    parser.add_argument("--out", help="Write output to this file (stdout if omitted)")
    parser.add_argument("--format", "-f", default="human", choices=["human", "json", "jsonl"],
                        help="Output format: human | json | jsonl")
    parser.add_argument("--include", action="append",
                        default=None,
                        help="For jsonl: which sections to include (repeat flag)")
    parser.add_argument("--graph-out",
                        help="Optional path to write a dependency graph JSON {nodes, edges}. If omitted and --out is given, a sibling <out>.graph.json is written.")
    parser.add_argument("--select-top", type=int, default=0,
                        help="Include top-N important files (uses scorer if available)")
    args = parser.parse_args()

    # Set default includes if not specified
    if args.include is None:
        include = ["meta", "ascii_tree", "ecosystem", "signals", "key_files", "folder_summaries", "tree", "important_files"]
    else:
        include = args.include

    # Scan the repo (NEW: pass top_n_important)
    data = scan_repo(args.repo, top_n_important=(args.select_top or None))

    # ----- write primary output -----
    fmt = args.format.lower()
    out_path = Path(args.out) if args.out else None

    if fmt == "jsonl":
        _write_jsonl(data, out_path, include)
        if out_path:
            print(f"Wrote {out_path}")
    else:
        if fmt == "json":
            text = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            text = _summarize_human(data)

        if out_path:
            out_path.write_text(text, encoding="utf-8")
            print(f"Wrote {out_path}")
        else:
            print(text)

    # ----- build and write dependency graph -----
    graph = build_dependency_graph(args.repo)

    if args.graph_out is not None:
        gpath = Path(args.graph_out)
    elif out_path is not None:
        if out_path.suffix:
            gpath = out_path.with_suffix(out_path.suffix + ".graph.json")
        else:
            gpath = out_path.with_suffix(".graph.json")
    else:
        gpath = Path("scan.graph.json")

    gpath.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {gpath}")

if __name__ == "__main__":
    main()

"""
Enhanced Claude client - sends scan.jsonl + graph + issues to Lambda
Usage: python claude_client.py <scan.jsonl> <repo_name> [--graph path] [--issues path]
"""

import sys
import json
import requests
from pathlib import Path
import argparse


LAMBDA_ENDPOINT = "your-lambda-url-here"  # Replace with actual endpoint


def load_jsonl(path):
    """Load JSONL file into single concatenated string"""
    lines = []
    with open(path, 'r') as f:
        for line in f:
            lines.append(line.strip())
    return '\n'.join(lines)


def load_json(path):
    """Load JSON file"""
    with open(path, 'r') as f:
        return json.load(f)


def generate_docs(scan_path, repo_name, graph_path=None, issues_path=None):
    """
    Call Lambda with all available data sources

    Args:
        scan_path: Path to scan.jsonl
        repo_name: Repository name (e.g. "user/repo")
        graph_path: Optional path to dependency graph JSON
        issues_path: Optional path to issues JSONL
    """

    # Load scan data (required)
    scan_data = load_jsonl(scan_path)

    # Load graph data (optional)
    graph_data = ""
    if graph_path and Path(graph_path).exists():
        graph_json = load_json(graph_path)
        # Summarize graph for prompt (don't send massive JSON)
        num_nodes = len(graph_json.get("nodes", []))
        num_edges = len(graph_json.get("edges", []))

        # Sample some important edges
        edges_sample = graph_json.get("edges", [])[:20]
        graph_data = f"""
Nodes: {num_nodes} files
Edges: {num_edges} import relationships

Sample dependencies:
{json.dumps(edges_sample, indent=2)}
"""
        print(f"✓ Loaded graph: {num_nodes} nodes, {num_edges} edges")

    # Load issues data (optional)
    issues_data = ""
    if issues_path and Path(issues_path).exists():
        issues_data = load_jsonl(issues_path)
        num_issues = len(issues_data.strip().split('\n'))
        print(f"✓ Loaded {num_issues} issues")

    # Build request payload
    payload = {
        "repo_data": scan_data,
        "graph_data": graph_data,
        "issues_data": issues_data,
        "repo_name": repo_name
    }

    print(f"\n🤖 Calling Claude API for {repo_name}...")
    print(f"   Scan data: {len(scan_data)} chars")
    print(f"   Graph data: {len(graph_data)} chars")
    print(f"   Issues data: {len(issues_data)} chars")

    # Call Lambda
    response = requests.post(
        LAMBDA_ENDPOINT,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60
    )

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    result = response.json()

    # Extract generated docs (could be multiple sections)
    architecture_doc = result.get("architecture_overview", "")

    print("\n✅ Documentation generated!")
    print(f"   Architecture overview: {len(architecture_doc)} chars")

    return {
        "architecture": architecture_doc,
        # Future: could return multiple doc types
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate onboarding docs using Claude API"
    )
    parser.add_argument("scan", help="Path to scan.jsonl")
    parser.add_argument("repo_name", help="Repository name (e.g., 'user/repo')")
    parser.add_argument("--graph", help="Optional: path to dependency graph JSON")
    parser.add_argument("--issues", help="Optional: path to issues JSONL")
    parser.add_argument("--out", help="Output file for architecture doc")

    args = parser.parse_args()

    # Auto-detect graph and issues if not specified
    scan_path = Path(args.scan)
    if not args.graph:
        # Try scan.jsonl.graph.json
        graph_candidate = scan_path.parent / f"{scan_path.name}.graph.json"
        if graph_candidate.exists():
            args.graph = str(graph_candidate)
            print(f"Auto-detected graph: {args.graph}")

    if not args.issues:
        # Try scan.issues.jsonl
        issues_candidate = scan_path.parent / "scan.issues.jsonl"
        if issues_candidate.exists():
            args.issues = str(issues_candidate)
            print(f"Auto-detected issues: {args.issues}")

    # Generate docs
    docs = generate_docs(
        args.scan,
        args.repo_name,
        args.graph,
        args.issues
    )

    # Save to file
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(docs["architecture"])
        print(f"\n📝 Saved to {args.out}")
    else:
        print("\n" + "="*80)
        print(docs["architecture"])
        print("="*80)


if __name__ == "__main__":
    main()

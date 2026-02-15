"""
Update existing Docusaurus site with Claude-generated onboarding doc
Usage: python generator.py <repo_path> <repo_name> [site_path]
"""

import json
import subprocess
import sys
import os
import anthropic
from pathlib import Path
import argparse
from .scanner import scan_repo, build_dependency_graph
from .github_client import GitHubClient, keyword_filter
from .main_old import _write_jsonl, _iter_jsonl_records
from .generate_graph_position import generate_graph_positions

SYSTEM_PROMPT = """You are a senior software architect. Given repository scan data, a dependency graph, \
and GitHub issues, generate a comprehensive architecture overview document for developer onboarding.

Your output should be well-structured Markdown covering:
1. **Project Overview** — What the project does, its purpose, and key technologies
2. **Architecture** — High-level system design, major components, and how they interact
3. **Directory Structure** — Key directories and what they contain
4. **Core Modules** — The most important files/modules and their responsibilities
5. **Dependency Flow** — How modules depend on each other (informed by the graph data)
6. **Common Patterns** — Recurring patterns, conventions, or idioms in the codebase
7. **Getting Started** — Key entry points for new developers
8. **Known Pain Points** — Common issues from GitHub issues data (if provided)

Write clearly and concisely. Use code references where helpful. \
Target audience is a new developer joining the team."""


def generate_all(repo_path: str, output_dir: str = "outputs",
                    gh_repo: str | None = None, gh_token: str | None = None,
                    issues_limit: int = 50, issues_keywords: list | None = None,
                    skip_github: bool = False, api_key: str | None = None):
    """
    Single command to generate all outputs

    Args:
        repo_path: Path to repository
        output_dir: Output directory for generated files
        gh_repo: GitHub repo in owner/name format (Optional)
        gh_token: Github token for private repos (Optional)
        issues_limit: Number of issues to fetch
        issues_keywords: Keywords for filtering issues
        skip_github: Skip GitHub issues discover entirely
        api_key: Anthropic API key (Optional)
    """

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print("\n🔍 1/4 Scanning repository...")
    scan_data = scan_repo(repo_path)

    # Write scan.jsonl
    scan_file = output_path / "scan.jsonl"
    with open(scan_file, 'w') as f:
        for record in _iter_jsonl_records(scan_data, include=["meta", "ascii_tree", "ecosystem", "signals", "key_files", "folder_summaries", "tree"]):
            f.write(json.dumps(record) + '\n')
    print(f"✅ Generated {scan_file}")

    print("\n📊 2/4 Building Dependency Graph...")
    graph = build_dependency_graph(repo_path)
    graph_file = output_path / "scan.jsonl.graph.json"
    graph_file.write_text(json.dumps(graph, indent=2))
    print(f"✅ Generated {graph_file}")

    in_path  = Path(output_dir) / "scan.jsonl.graph.json"
    out_path = Path(output_dir).parent / "site" / "static" / "graph_with_pos.json"
    generate_graph_positions(str(in_path), str(out_path))
    print(f"✅ Visualised graph with edges and nodes")

    issues_file = None
    if skip_github:
        print("\n⏭️ 3/4 Skipping GitHub issues (--skip_github flag set)")
    elif not gh_repo:
        print("\n⏭️ 3/4 Skipping GitHub issues (no repository name detected)")
    elif issues_limit <= 0:
        print("\n⏭️ 3/4 Skipping GitHub issues (issues_limit = 0)")
    else:
        print(f"\n🐙 3/4 Fetching GitHub issues...")
        try:
            from .github_client import DEFAULT_KEYWORDS
            keywords = issues_keywords if issues_keywords else DEFAULT_KEYWORDS['body'] + DEFAULT_KEYWORDS['labels']
            client = GitHubClient(token=gh_token)
            raw_issues = client.fetch_all_issues(gh_repo, limit=issues_limit, include_body=True)
            filtered = keyword_filter(raw_issues, keywords, min_hits=1)

            issues_file = output_path / "scan.issues.jsonl"
            with open(issues_file, 'w') as f:
                for issue in filtered:
                    f.write(json.dumps(issue) + '\n')
            print(f"✅ Generated {issues_file}")

        except ValueError as e:
            # Repository not found - likely private without token
            print(f"⚠️ Warning: Could not access GitHub repository: {e}")
            print("   💡 For private repos:")
            print("      - Use --skip-github flag to skip issues")
            print("      - Or set GITHUB_TOKEN environment variable")
            print("      - Or run: unbored config set github_token <your-token>")
            print("   ⏭️  Continuing without GitHub issues...")

        except RuntimeError as e:
            # GitHub API error
            print(f"⚠️  Warning: GitHub API error: {e}")
            print("   ⏭️  Continuing without GitHub issues...")

        except Exception as e:
            # Catch-all for unexpected errors
            print(f"⚠️  Warning: Unexpected error fetching issues: {e}")
            print("   ⏭️  Continuing without GitHub issues...")

    print("\n🤖 4/4 Generating documentation with Claude...")
    onboarding_doc = send_to_claude(
        scan_file,
        gh_repo or repo_path,
        graph_file=graph_file,
        issues_file=issues_file,
        api_key=api_key,
    )

    return output_path, onboarding_doc


def send_to_claude(scan_file, repo_name, graph_file=None, issues_file=None, api_key=None):
    """
    Call Claude API directly using the Anthropic SDK.

    Args:
        scan_file: Path to scan.jsonl
        repo_name: Repository name
        graph_file: Optional path to graph JSON
        issues_file: Optional path to issues JSONL
        api_key: Optional Anthropic API key
    """
    # Resolve API key
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        # Try config file as last resort
        try:
            from .config import load_config
            config = load_config()
            resolved_key = config.get("anthropic_api_key")
        except Exception:
            pass

    if not resolved_key:
        print("❌ No Anthropic API key found.")
        print("   💡 Provide your API key using one of these methods:")
        print("      1. unbored config set anthropic_api_key <your-key>")
        print("      2. export ANTHROPIC_API_KEY=<your-key>")
        print("      3. unbored --api-key <your-key>")
        return None

    try:
        # Load scan data (required)
        repo_data = Path(scan_file).read_text()

        # Load graph data (optional)
        graph_data = ""
        if graph_file and Path(graph_file).exists():
            graph_json = json.loads(Path(graph_file).read_text())
            num_nodes = len(graph_json.get("nodes", []))
            num_edges = len(graph_json.get("edges", []))

            # Summarize graph (don't send full JSON)
            edges_sample = graph_json.get("edges", [])[:30]
            graph_data = f"""
Dependency Graph Summary:
- {num_nodes} files analyzed
- {num_edges} import relationships found

Sample import relationships:
{json.dumps(edges_sample, indent=2)}
"""
            print(f"   ✓ Including graph: {num_nodes} nodes, {num_edges} edges")

        # Load issues data (optional)
        issues_data = ""
        if issues_file and Path(issues_file).exists():
            issues_lines = Path(issues_file).read_text().strip().split('\n')
            issues_data = '\n'.join(issues_lines[:20])  # Limit to 20 issues
            print(f"   ✓ Including {len(issues_lines)} issues")

        # Build the user message
        user_message = f"Repository: {repo_name}\n\n"
        user_message += f"## Repository Scan Data\n{repo_data}\n\n"
        if graph_data:
            user_message += f"## {graph_data}\n\n"
        if issues_data:
            user_message += f"## GitHub Issues\n{issues_data}\n\n"

        print(f"   Payload size: {len(user_message)} chars")

        client = anthropic.Anthropic(api_key=resolved_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = response.content[0].text
        print("✅ Onboarding doc generated")
        return result_text

    except anthropic.AuthenticationError:
        print("❌ Invalid Anthropic API key.")
        print("   💡 Check your key and update it:")
        print("      unbored config set anthropic_api_key <your-key>")
        return None

    except anthropic.RateLimitError:
        print("❌ Anthropic API rate limit exceeded. Please wait and try again.")
        return None

    except Exception as e:
        print(f"❌ Error calling Claude API: {e}")
        return None


def update_existing_site(onboarding_doc, repo_name, site_path):
    """Update existing Docusaurus site"""
    print("📝 Updating Docusaurus site...")

    site_dir = Path(site_path)
    if not site_dir.exists():
        print(f"❌ Site directory {site_path} not found")
        return False

    # Create intro.md
    intro_content = f"""---
sidebar_position: 1
---

# {repo_name} - Architecture Overview

{onboarding_doc}

---

*This documentation was automatically generated by unbored.AI using Claude.*
"""

    # Update docs/intro.md
    docs_path = site_dir / "docs" / "intro.md"
    docs_path.parent.mkdir(exist_ok=True)
    docs_path.write_text(intro_content)

    print(f"✅ Updated {docs_path}")

    # Update title in docusaurus.config.ts if it exists
    config_path = site_dir / "docusaurus.config.ts"
    if config_path.exists():
        config_content = config_path.read_text()
        if "title: 'Ghost Onboarder'," in config_content:
            updated_config = config_content.replace(
                "title: 'Ghost Onboarder',",
                f"title: '{repo_name} Documentation',"
            ).replace(
                "tagline: 'Turn any repo into a self-explaining codebase',",
                f"tagline: 'Auto-generated documentation for {repo_name}',"
            )
            config_path.write_text(updated_config)
            print(f"✅ Updated site title")

    return True


def main():
    parser = argparse.ArgumentParser(description="Ghost Onboarder - Generate onboarding docs")
    parser.add_argument("repo_path", nargs='?', default=".",
                       help="Repository path (default: current directory)")
    parser.add_argument("--output", "-o", default="outputs",
                       help="Output directory (default: outputs)")
    parser.add_argument("--gh-repo",
                       help="GitHub repo (owner/name) for issues")
    parser.add_argument("--gh-token",
                       help="GitHub token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--api-key",
                       help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--issues-limit", type=int, default=50,
                       help="Number of issues to fetch (default: 50)")
    parser.add_argument("--site-path", default="ghost-onboarder-site",
                       help="Docusaurus site path (default: ghost-onboarder-site)")

    args = parser.parse_args()

    print(f"🏁 Generating docs for {args.repo_path}")
    print()

    # Generate all outputs
    output_path, onboarding_doc = generate_all(
        repo_path=args.repo_path,
        output_dir=args.output,
        gh_repo=args.gh_repo,
        gh_token=args.gh_token,
        issues_limit=args.issues_limit,
        api_key=args.api_key,
    )

    # Update site
    if not update_existing_site(onboarding_doc, args.gh_repo or args.repo_path, args.site_path):
        sys.exit(1)

    print()
    print("🎉 Documentation generated successfully!")
    print(f"💡 Start site: cd {args.site_path} && npm run build && npm run serve")

if __name__ == "__main__":
    main()

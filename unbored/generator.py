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
and GitHub issues, generate multi-page onboarding documentation for developer onboarding.

Analyze the codebase and identify logical subsystems autonomously. Output a JSON array of page objects — \
no other text, no markdown fences, just the raw JSON array. Cap the number of pages at 6.

Always include:
- An "intro.md" page covering Project Overview and Architecture (sidebar_position: 1)
- One page per major logical module or subsystem you identify

Each page object must have these exact fields:
{
  "filename": "intro.md",
  "title": "Overview",
  "sidebar_position": 1,
  "content": "...full markdown content for this page..."
}

Rules for content:
- Write well-structured Markdown per page
- intro.md must cover: project purpose, key technologies, high-level architecture, directory structure, getting started
- Each module page covers: what it does, key files/classes, how it connects to other modules, any gotchas
- Use code references where helpful (file paths, function names)
- Target audience is a new developer joining the team
- If GitHub issues are provided, include a "Known Pain Points" section on the relevant page (intro.md if unsure)

Output ONLY the JSON array. No preamble, no explanation, no markdown code fences."""


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
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = response.content[0].text.strip()

        # Strip markdown code fences if Claude wrapped the JSON
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[-1]  # drop opening fence line
            if result_text.endswith("```"):
                result_text = result_text[: result_text.rfind("```")].strip()

        # Parse JSON array of page dicts
        try:
            pages = json.loads(result_text)
            if not isinstance(pages, list):
                raise ValueError("Expected JSON array")
            print(f"✅ Generated {len(pages)} documentation page(s)")
            return pages
        except (json.JSONDecodeError, ValueError) as e:
            # Response may have been truncated — try to salvage any complete page objects
            print(f"⚠️  Could not parse full JSON response ({e}), attempting partial recovery...")
            decoder = json.JSONDecoder()
            rest = result_text.lstrip().lstrip("[").lstrip()
            salvaged = []
            while rest:
                try:
                    obj, idx = decoder.raw_decode(rest)
                    if isinstance(obj, dict) and "filename" in obj and "content" in obj:
                        salvaged.append(obj)
                    rest = rest[idx:].lstrip().lstrip(",").lstrip()
                except json.JSONDecodeError:
                    break
            if salvaged:
                print(f"✅ Recovered {len(salvaged)} page(s) from partial response")
                return salvaged
            print("⚠️  Could not recover any pages — response may have been cut off")
            return [{"filename": "intro.md", "title": "Overview", "sidebar_position": 1,
                     "content": "# Documentation\n\nDocumentation generation was incomplete (response truncated). "
                                "Please run `unbored` again."}]

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


def update_existing_site(pages, repo_name, site_path):
    """Update existing Docusaurus site with multi-page documentation.

    Args:
        pages: List of {filename, title, sidebar_position, content} dicts from Claude
        repo_name: Repository name (used for site title update)
        site_path: Path to the Docusaurus site directory
    """
    print("📝 Updating Docusaurus site...")

    site_dir = Path(site_path)
    if not site_dir.exists():
        print(f"❌ Site directory {site_path} not found")
        return False

    docs_dir = site_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    # Clear previously generated .md files from docs/
    for existing_md in docs_dir.glob("*.md"):
        existing_md.unlink()

    # Write each page with frontmatter
    for page in pages:
        filename = page.get("filename", "intro.md")
        title = page.get("title", "Documentation")
        sidebar_position = page.get("sidebar_position", 1)
        content = page.get("content", "")

        # Build frontmatter
        # format: md forces plain CommonMark parsing instead of MDX,
        # preventing acorn parse errors on curly braces / angle brackets
        # that Claude may emit in generated content.
        frontmatter_lines = [
            "---",
            f"sidebar_position: {sidebar_position}",
            f"title: \"{title}\"",
            "format: md",
        ]
        # Root page gets slug: / so docs become the site root (v0.6.0)
        if filename == "intro.md":
            frontmatter_lines.append("slug: /")
        frontmatter_lines.append("---")
        frontmatter = "\n".join(frontmatter_lines)

        page_content = f"{frontmatter}\n\n{content}\n\n---\n\n*This documentation was automatically generated by unbored.AI using Claude.*\n"

        page_path = docs_dir / filename
        page_path.write_text(page_content)
        print(f"✅ Written {page_path.name}")

    # Update title in docusaurus.config.ts if it exists
    config_path = site_dir / "docusaurus.config.ts"
    if config_path.exists():
        config_content = config_path.read_text()
        if "title: 'unbored - Claude Builder HackASU'," in config_content or "title: 'Ghost Onboarder'," in config_content:
            updated_config = config_content.replace(
                "title: 'unbored - Claude Builder HackASU',",
                f"title: '{repo_name} Documentation',"
            ).replace(
                "title: 'Ghost Onboarder',",
                f"title: '{repo_name} Documentation',"
            ).replace(
                "tagline: 'Turn any repo into a self-explaining codebase',",
                f"tagline: 'Auto-generated documentation for {repo_name}',"
            )
            config_path.write_text(updated_config)
            print(f"✅ Updated site title to '{repo_name} Documentation'")

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

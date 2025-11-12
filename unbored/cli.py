"""
unBored AI — One command onboarding documentation generator
"""

import os
import sys
import webbrowser
import subprocess
import argparse
from pathlib import Path
from .generator import generate_all, send_to_claude, update_existing_site

def update_gitignore(repo_path):
    """Add .unbored to .gitignore if not already present"""
    gitignore_path = Path(repo_path) / ".gitignore"

    # Read existing content
    content = ""
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".unbored" in content:
            return  # Already there

    # Add .unbored to .gitignore
    try:
        with open(gitignore_path, "a") as f:
            # Add newline before if file doesn't end with one
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("# unbored.AI generated documentation\n")
            f.write(".unbored/\n")
        print("✅ Added .unbored/ to .gitignore")
    except Exception as e:
        print(f"⚠️  Could not update .gitignore: {e}")

def main():
    """Main CLI entry point - runs from current directory"""

    parser = argparse.ArgumentParser(
            description="unbored.AI - Generate onboarding documentation for any repository"
    )
    parser.add_argument(
            "--skip_github",
            action="store_true",
            help="Skip GitHub issues discovery (useful for private repos without access tokens)"
    )
    args = parser.parse_args()

    # Get current working directory
    repo_path = os.getcwd()

    # Infer repo name from git remote or directory name
    repo_name = Path(repo_path).name
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract username/repo from git URL
            if "github.com" in url:
                parts = url.split("github.com")[-1]
                parts = parts.lstrip(":/").rstrip("/")
                parts = parts.replace(".git", "")
                repo_name = parts
    except:
        pass

    print("🤖 unbored.AI")
    print(f"📁 Repository: {repo_path}")
    print(f"📝 Detected Name: {repo_name}")
    print()

    # Determine paths relative to this package installation
    package_dir = Path(__file__).parent
    template_site = package_dir / "template-site"
    output_dir = Path(repo_path) / ".unbored"
    site_dir = output_dir / "site"

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Add .unbored to .gitignore
    update_gitignore(repo_path)

    # Copy template site if needed
    if not site_dir.exists():
        print("📦 Setting up documentation site...")
        if template_site.exists():
            import shutil
            shutil.copytree(template_site, site_dir)
            # Install npm dependencies
            subprocess.run(["npm", "install"], cwd=site_dir, check=False)
        else:
            print("⚠️ Warning: Template site not found, skipping site generation")

    # Run pipeline
    try:
        # Generate all analysis data
        generate_all(
                repo_path = repo_path,
                output_dir = str(output_dir / "outputs"),
                gh_repo=repo_name if not args.skip_github else None,
                skip_github=args.skip_github
        )

        # Send to Claude and get documentation
        scan_file = output_dir / "outputs" / "scan.jsonl"
        graph_file = output_dir / "outputs" / "scan.jsonl.graph.json"

        if scan_file.exists():
            print("\n🤖 4/4 Generating documentation with Claude AI...")
            onboarding_doc = send_to_claude(
                scan_file=str(scan_file),
                repo_name=repo_name,
                graph_file=str(graph_file) if graph_file.exists() else None
            )

            if onboarding_doc and site_dir.exists():
                update_existing_site(onboarding_doc, repo_name, str(site_dir))

                # Start the dev server
                print("\n🚀 Starting documentation server...")
                print(f"📖 Opening documentation at http://localhost:3000")

                # Start npm
                subprocess.run(["npm", "start"], cwd=site_dir)

                print("\n\nℹ️ Once done reading the documentation docs, use Ctrl+C to stop the docusaurus server!")
            else:
                print("\n✅ Documentation generated in:", output_dir)
        else:
            print("❌ Scan failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

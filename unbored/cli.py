"""
unBored AI — One command onboarding documentation generator
"""

import os
import sys
import json
import webbrowser
import subprocess
from pathlib import Path
from .scanner import scan_repo, build_dependency_graph
from .generator import generate_all, send_to_claude, update_existing_site

def main():
    """Main CLI entry point - runs from current directory"""

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
                parts = url.split("github.com")[1].strip("/").replace(".git", "")
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
    output_dir = Path(repo_path) / ".ghost-onboarder"
    site_dir = output_dir / "site"

    # Create output directory
    output_dir.mkdir(exist_ok=True)

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
                gh_repo=repo_name
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

                # Open browser
                webbrowser.open("http://localhost:3000")

                # Start npm
                subprocess.run(["npm", "start"], cwd=site_dir)
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

"""
unBored AI — One command onboarding documentation generator
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path
from .generator import generate_all, update_existing_site
from .config import load_config, save_config, resolve_token

def _save_snapshot(output_dir: Path):
    """Save current git commit hash and timestamp to generation_snapshot.json."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return
        commit = result.stdout.strip()
        snapshot = {
            "git_commit": commit,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "generation_snapshot.json").write_text(json.dumps(snapshot, indent=2))
    except Exception:
        pass


def _check_diff(repo_path: str, output_dir: Path):
    """Return (status, lines_changed) based on git diff since last generation."""
    snapshot_file = output_dir / "generation_snapshot.json"
    if not snapshot_file.exists():
        return ("no_snapshot", 0)

    try:
        stored_commit = json.loads(snapshot_file.read_text()).get("git_commit", "")
    except Exception:
        return ("no_snapshot", 0)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ("no_git", 0)
        current_commit = result.stdout.strip()
    except Exception:
        return ("no_git", 0)

    if current_commit == stored_commit:
        return ("unchanged", 0)

    # Diff only source-significant files
    source_globs = ["*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.go", "*.java", "*.rb", "*.rs"]
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--shortstat", stored_commit, "HEAD", "--"] + source_globs,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines_changed = 0
        if diff_result.returncode == 0 and diff_result.stdout.strip():
            for part in diff_result.stdout.split(","):
                part = part.strip()
                if "insertion" in part or "deletion" in part:
                    try:
                        lines_changed += int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
    except Exception:
        lines_changed = 0

    return ("changed", lines_changed)


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


def _mask(value: str) -> str:
    """Mask a token for display, showing only last 4 chars."""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def handle_config(args):
    """Handle the 'config' subcommand."""
    if args.config_action == "set":
        valid_keys = {"github_token", "anthropic_api_key"}
        if args.key not in valid_keys:
            print(f"❌ Unknown config key: {args.key}")
            print(f"   Valid keys: {', '.join(sorted(valid_keys))}")
            sys.exit(1)
        config = load_config()
        config[args.key] = args.value
        save_config(config)
        print(f"✅ Saved {args.key}")

    elif args.config_action == "show":
        config = load_config()
        if not config:
            print("No configuration found.")
            print(f"Config file: {Path.home() / '.unbored' / 'config.yaml'}")
            return
        print("Current configuration:")
        for key, value in config.items():
            print(f"  {key}: {_mask(str(value))}")

    elif args.config_action == "clear":
        save_config({})
        print("✅ Configuration cleared")

    else:
        print("Usage: unbored config {set,show,clear}")
        sys.exit(1)


def main():
    """Main CLI entry point - runs from current directory"""

    parser = argparse.ArgumentParser(
            description="unbored.AI - Generate onboarding documentation for any repository"
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- config subcommand ---
    config_parser = subparsers.add_parser("config", help="Manage stored configuration")
    config_sub = config_parser.add_subparsers(dest="config_action")

    set_parser = config_sub.add_parser("set", help="Set a config value")
    set_parser.add_argument("key", help="Config key (github_token, anthropic_api_key)")
    set_parser.add_argument("value", help="Config value")

    config_sub.add_parser("show", help="Show current config (masked)")
    config_sub.add_parser("clear", help="Clear all config")

    # --- view subcommand ---
    subparsers.add_parser("view", help="Launch existing documentation site without regenerating")

    # --- main pipeline flags ---
    parser.add_argument(
            "--skip_github",
            action="store_true",
            help="Skip GitHub issues discovery (useful for private repos without access tokens)"
    )
    parser.add_argument(
            "--github-token",
            help="GitHub personal access token (overrides env var and config)"
    )
    parser.add_argument(
            "--api-key",
            help="Anthropic API key (overrides env var and config)"
    )

    args = parser.parse_args()

    # Route to config handler
    if args.command == "config":
        handle_config(args)
        return

    # Route to view handler
    if args.command == "view":
        site_dir = Path(os.getcwd()) / ".unbored" / "site"
        docs_dir = site_dir / "docs"
        if not site_dir.exists() or not any(docs_dir.glob("*.md")):
            print("❌ No documentation found. Run `unbored` first to generate it.")
            sys.exit(1)
        print("📖 Opening documentation at http://localhost:3000")
        subprocess.run(["npm", "start"], cwd=site_dir)
        return

    # Resolve tokens
    github_token = resolve_token(args.github_token, "GITHUB_TOKEN", "github_token")
    api_key = resolve_token(args.api_key, "ANTHROPIC_API_KEY", "anthropic_api_key")

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
    import shutil
    if not site_dir.exists():
        print("📦 Setting up documentation site...")
        if template_site.exists():
            shutil.copytree(template_site, site_dir)
            # Install npm dependencies
            subprocess.run(["npm", "install"], cwd=site_dir, check=False)
        else:
            print("⚠️ Warning: Template site not found, skipping site generation")
    elif template_site.exists():
        # Sync theme files that may have changed since the site was first created
        for rel in ["src/css/custom.css", "docusaurus.config.ts"]:
            src = template_site / rel
            dst = site_dir / rel
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # Remove old homepage files that are no longer part of the template
        for stale in [
            "src/pages/index.tsx",
            "src/pages/index.module.css",
            "src/pages/markdown-page.md",
        ]:
            p = site_dir / stale
            if p.exists():
                p.unlink()
        stale_dir = site_dir / "src/components/HomepageFeatures"
        if stale_dir.exists():
            shutil.rmtree(stale_dir)

    # Check for changes since last generation
    status, lines_changed = _check_diff(repo_path, output_dir / "outputs")
    if status == "unchanged":
        print("✅ No changes since last generation. Launching existing docs...")
        subprocess.run(["npm", "start"], cwd=site_dir)
        return
    elif status == "changed":
        MINOR_THRESHOLD = 20
        if lines_changed <= MINOR_THRESHOLD:
            print(f"⚠️  Minor changes detected ({lines_changed} lines changed since last generation).")
            answer = input("Regenerate documentation? [y/N] ").strip().lower()
            if answer != "y":
                print("Launching existing docs...")
                subprocess.run(["npm", "start"], cwd=site_dir)
                return

    # Run pipeline
    try:
        # Generate all analysis data and Claude documentation
        output_path, onboarding_doc = generate_all(
                repo_path=repo_path,
                output_dir=str(output_dir / "outputs"),
                gh_repo=repo_name if not args.skip_github else None,
                gh_token=github_token,
                skip_github=args.skip_github,
                api_key=api_key,
        )

        if onboarding_doc and site_dir.exists():
            # onboarding_doc is a list of {filename, title, sidebar_position, content} dicts
            update_existing_site(onboarding_doc, repo_name, str(site_dir))
            _save_snapshot(output_dir / "outputs")

            # Start the dev server
            print("\n🚀 Starting documentation server...")
            print(f"📖 Opening documentation at http://localhost:3000")

            # Start npm
            subprocess.run(["npm", "start"], cwd=site_dir)

            print("\n\nℹ️ Once done reading the documentation docs, use Ctrl+C to stop the docusaurus server!")
        elif not onboarding_doc:
            print("\n⚠️  Documentation generation returned empty. Check your API key configuration.")
            print("   💡 Set your Anthropic API key:")
            print("      unbored config set anthropic_api_key <your-key>")
            print("      or: export ANTHROPIC_API_KEY=<your-key>")
            print("      or: unbored --api-key <your-key>")
        else:
            print("\n✅ Documentation generated in:", output_dir)

    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

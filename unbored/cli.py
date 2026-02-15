"""
unBored AI — One command onboarding documentation generator
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from .generator import generate_all, update_existing_site
from .config import load_config, save_config, resolve_token

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
            update_existing_site(onboarding_doc, repo_name, str(site_dir))

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

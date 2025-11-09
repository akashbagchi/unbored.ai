# Ghost Onboarder

Automated onboarding documentation generator that transforms GitHub repositories into comprehensive documentation sites with AI-generated architecture overviews.

## Quick Start

```bash
# 1. Generate documentation for a repository
python generator.py ../path/to/repo username/repo-name

# 2. Start documentation site
cd ghost-onboarder-site
npm start

# 3. View at http://localhost:3000
```

## What It Does

- **Architecture Overview**: AI-generated system design explanations
- **Interactive Graph**: Visual repository structure and dependencies
- **Docusaurus Site**: Professional, searchable documentation

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+

### Setup
```bash
# Python dependencies
pip install -r requirements.txt

# Site dependencies
cd ghost-onboarder-site && npm install
```

## Usage

### Full Pipeline
```bash
python generator.py <repo_path> <repo_name> [site_path]

# Example
python generator.py ../my-project johndoe/my-project
```

### Manual Steps

**Scan repository:**
```bash
python cli/main.py --repo ../my-project --format jsonl --out outputs/scan.jsonl
```

**Generate documentation (uses AWS Lambda + Claude):**
```bash
python cli/claude_client.py outputs/scan.jsonl johndoe/my-project
```

**Start site:**
```bash
cd ghost-onboarder-site && npm start
```

## Project Structure

```
ghost-onboarder/
├── cli/
│   ├── main.py              # Repository scanner (entry point)
│   ├── scanner.py           # File analysis + dependency graphs
│   ├── claude_client.py     # AWS Lambda/Claude integration
│   ├── github_client.py     # GitHub issues fetcher
│   └── ...
├── generator.py             # Full pipeline orchestrator
├── ghost-onboarder-site/    # Docusaurus site
│   ├── docs/intro.md        # Auto-generated overview
│   └── src/pages/graph.tsx  # Interactive graph view
└── outputs/                 # Scan results (JSONL + graph JSON)
```

## CLI Options

### Basic Scanning
```bash
python cli/main.py --repo <path> --format <json|jsonl|md> --out <file>
```

- `--repo`: Repository path to scan
- `--format`: Output format (json/jsonl/md, default: json)
- `--out`: Output file path

### GitHub Issues Integration
```bash
python -m cli.main \
  --repo ../tmprepo/<repo-name> \
  --out ../outputs/scan.md \
  --format human \
  --gh-repo <username/reponame> \
  --issues-limit <number> \
  --issues-format json \
  --issues-min-hits 1 \
  --issues-out ../outputs/issues.json
```

**Issues options:**
- `--gh-repo`: GitHub repository (format: `username/repo`)
- `--issues-limit`: Number of closed issues to fetch
- `--issues-format`: Output format for issues (json/jsonl)
- `--issues-min-hits`: Minimum keyword matches to include issue
- `--issues-out`: Output file for filtered issues

**Example:**
```bash
python -m cli.main \
  --repo ../tmprepo/my-app \
  --out ../outputs/scan.md \
  --format human \
  --gh-repo johndoe/my-app \
  --issues-limit 50 \
  --issues-format json \
  --issues-min-hits 2 \
  --issues-out ../outputs/issues.json
```

Fetches closed GitHub issues filtered by setup/install/config keywords for FAQ generation.

## Tech Stack

- **Backend**: Python, argparse, tree-sitter
- **AI**: Claude (Anthropic Sonnet 4) via AWS Bedrock/Lambda
- **Frontend**: Docusaurus, React, TypeScript, React Flow
- **GitHub**: PyGithub for issues/PR analysis

## Development

```bash
# Test scanner
python cli/main.py --repo ../tmprepo/sample-repo --out outputs/test.md

# Test with GitHub issues
python -m cli.main --repo ../tmprepo/sample-repo --out outputs/scan.md --format human \
  --gh-repo owner/repo --issues-limit 20 --issues-out outputs/issues.json

# Development server
cd ghost-onboarder-site && npm run start

# Production build
cd ghost-onboarder-site && npm run build
```


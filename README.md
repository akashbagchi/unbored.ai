# unbored.AI

Automated onboarding documentation generator. Scans a GitHub repository, builds a dependency graph, fetches relevant issues, and produces an architecture overview via Claude — served as a Docusaurus site.

## Quick Start

```bash
# Install
pip install git+https://github.com/akashbagchi/unbored.ai.git

# Set your Anthropic API key (one-time)
unbored config set anthropic_api_key sk-ant-...

# Run from any repository
cd /path/to/your/repo
unbored
```

The CLI scans the repo, calls Claude, and opens a documentation site at `http://localhost:3000`.

## What It Generates

- **Architecture Overview** — AI-generated breakdown of system design, components, and tech stack.
- **Interactive Dependency Graph** — Visual map of imports and module relationships (React Flow).
- **Documentation Site** — Searchable Docusaurus site with the above content.

## Configuration

Tokens are resolved in order: **CLI flag > environment variable > config file**.

### API Keys

An Anthropic API key is required. A GitHub token is optional (needed for private repos or higher rate limits).

```bash
# Store keys persistently (~/.unbored/config.yaml)
unbored config set anthropic_api_key sk-ant-...
unbored config set github_token ghp_...

# View stored config (values are masked)
unbored config show

# Clear all stored config
unbored config clear
```

Alternatively, use environment variables:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
```

Or pass per-run via CLI flags:

```bash
unbored --api-key sk-ant-... --github-token ghp_...
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--api-key` | Anthropic API key (overrides env and config) |
| `--github-token` | GitHub PAT (overrides env and config) |
| `--skip_github` | Skip GitHub issue discovery entirely |

## Pipeline

```
Target Repo
  -> scanner.py         Scan file tree, detect ecosystem, read key files
  -> build_dependency_graph  Extract JS/TS/Python imports into a NetworkX graph
  -> generate_graph_positions  Spring layout with community detection
  -> github_client.py   Fetch and filter closed issues by onboarding keywords
  -> generator.py       Send scan + graph + issues to Claude, receive architecture overview
  -> update_existing_site  Write generated content into Docusaurus template
  -> npm start           Serve documentation site
```

## Project Structure

```
unbored.ai/
├── unbored/
│   ├── cli.py                      # CLI entry point (unbored command)
│   ├── config.py                   # Token/config management (~/.unbored/config.yaml)
│   ├── scanner.py                  # Repository analysis
│   ├── generator.py                # Claude API integration, site updater
│   ├── github_client.py            # GitHub issue fetching (PyGithub)
│   ├── generate_graph_positions.py # Graph layout (NetworkX + spring layout)
│   ├── main_old.py                 # Legacy CLI (manual pipeline steps)
│   └── template-site/              # Docusaurus template
│       ├── docs/intro.md           # AI-generated architecture overview
│       ├── src/pages/graph.tsx     # Interactive dependency graph (React Flow)
│       └── static/graph_with_pos.json
├── requirements.txt
├── setup.py
├── CHANGELOG.md
└── README.md
```

## Output

Running `unbored` creates a `.unbored/` directory (auto-added to `.gitignore`):

```
.unbored/
├── outputs/
│   ├── scan.jsonl              # Repository structure and metadata
│   ├── scan.jsonl.graph.json   # Dependency graph (nodes + edges)
│   └── scan.issues.jsonl       # Filtered GitHub issues (if available)
└── site/                       # Docusaurus site with generated content
```

## Requirements

- Python 3.8+
- Node.js 20+ (for the documentation site)
- Git
- An [Anthropic API key](https://console.anthropic.com/)

## Tech Stack

**Pipeline:** Python, Anthropic SDK (Claude Sonnet 4), NetworkX, PyGithub, PyYAML

**Documentation Site:** Docusaurus 3.9, React 19, React Flow 11, TypeScript

## Development

```bash
# Install in editable mode
pip install -e .

# Run the template site directly
cd unbored/template-site
npm install
npm run start        # Dev server
npm run build        # Production build
npm run typecheck    # Type checking
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes and push
4. Open a Pull Request

## License

MIT License with Attribution Requirement.

Copyright (c) 2025 Akash Bagchi, Akshaya Nadathur, Pranjal Padakannaya, Sachin SS

When using, modifying, or distributing this software, include attribution to the original authors and a link to this repository. See [LICENSE](LICENSE) for details.

## Links

- [Pitch Deck](https://www.figma.com/deck/ryyAt60shYMnkMtUzyuecJ/unbored-presentation?node-id=1-32&viewport=-158%2C-121%2C0.72&t=tw2HYoP7KJmOaFKi-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1)
- [Demo Video](https://youtu.be/oMcnYGHypfU)

---

*Built during HackASU 2025 (Claude Builder Club @ ASU)*

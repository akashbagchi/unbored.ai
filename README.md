# unbored.AI

**Automated onboarding documentation generator that transforms any GitHub repository into a comprehensive documentation site with AI-generated architecture overviews.**

## 🚀 Quick Start

Generate beautiful documentation for any repository in 3 steps:

```bash
# 1. Install unbored
pip install unbored

# 2. Navigate to your repository
cd /path/to/your/repo

# 3. Generate and view onboarding documentation
unbored

# That's it! Opens documentation at http://localhost:3000
```

Our tool automatically:
- Scans your repository structure
- Generates AI-powered onboarding documentation
- Creates an interactive documentation website
- Opens it in your browser

## 🎯 What It Does

unbored.AI automatically creates:

- **📋 Architecture Overview**: AI-generated explanation of system design, tech stack, and component responsibilities
- **🗂️ Interactive Graph View**: Visual representation of repository structure and dependencies
- **📚 Professional Documentation Site**: Clean, searchable Docusaurus site with modern UI

## 🏗️ How It Works

```
Repository → Scanner → Claude AI → Documentation Site
     ↓           ↓         ↓            ↓
   File tree   Analyze   Generate    Beautiful
   Structure   Content   Overview     Docs
```

### Automated Pipeline

1. **Repository Scanning** (`cli/main.py`): Analyzes file structure, extracts key information
2. **AI Processing** (`generator.py`): Sends structured data to Claude API for documentation generation
3. **Site Generation**: Updates existing Docusaurus site with AI-generated content

## 📁 Project Structure

```
unbored.ai/
├── unbored/                            # Core package
│   ├── template_site/                  # Docusaurus template
│   ├── claude_client.py
│   ├── cli.py                          # Main CLI entry point (unbored command)
│   ├── generate_graph_positions.py     # Graph layout
│   ├── generator.py
│   ├── github_client.py
│   ├── main_old.py
│   └── scanner.py                      # Repository analysis
├── MANIFEST.in
├── README.md
├── requirements.txt
└── setup.py
```

## 🛠️ Installation

```bash
pip install git+https://github.com/akashbagchi/unbored.ai.git@v0.2.0
```

**Requirements:**
- Python 3.8+
- Node.js 16+ (for documentation site)
- Git (for repository detection)

## 📖 Usage

### Basic Usage (Recommended)

```bash
cd your-project
unbored
```

### Advanced: Manual Pipeline

If you need more control:
```bash
# 1. Generate scan data
python -m unbored.main_old --repo . --out .unbored/scan.jsonl

# 2. Generate dependency graph
# (automatically created as scan.jsonl.graph.json)

# 3. Generate documentation
python -m unbored.claude_client .unbored/scan.jsonl your-username/repo-name
```

## 🔧 Configuration

> [!WARNING]
> This tool currently uses a pre-configured AWS Lambda endpoint set-up by one of our core developers. This is subject to change at any time due to cost constraints, which would require users to provide their own endpoints and/or API keys. Please be mindful of the same with your usage.

### API Setup
The pipeline uses a pre-configured AWS Lambda endpoint. No additional API key setup required.

### Customization
All generated files are in `.unbored/` directory (automatically added to `.gitignore`):
- Modify `site/docs/` for custom documentation pages
- Edit `site/docusaurus.config.ts` for site customization
- Update `outputs/` for raw analysis data

## 📂 Output Structure

Running `unbored` creates a `./unbored/` directory in your repository:

```
.unbored/
├── outputs/
│   ├── scan.jsonl              # Repository analysis
│   ├── scan.jsonl.graph.json   # Dependency graph
│   └── scan.issues.jsonl       # GitHub issues (if available)
└── site/                       # Docusaurus documentation site
    ├── docs/intro.md           # AI-generated architecture overview
    ├── src/pages/graph.tsx     # Interactive dependency graph
    └── static/graph_with_pos.json  # Graph visualization data
```

**Note:** `.unbored/` is automatically added to your `.gitignore`

## 🎯 Use Cases

- **🏢 Enterprise Onboarding**: Reduce new developer ramp-up time from weeks to days
- **📖 Open Source Projects**: Auto-generate comprehensive documentation for contributors
- **🔄 Legacy Codebases**: Quickly document undocumented projects
- **📚 Code Reviews**: Provide architectural context for reviewers

## 🧰 Tech Stack

**Core Pipeline:**
- Python (scanning, API integration)
- Claude AI (Anthropic Sonnet 4)
- AWS Lambda (Claude API proxy)
- NetworkX (graph analysis)
- Typer (CLI framework)

**Documentation Site:**
- Docusaurus (React-based)
- React Flow (interactive graphs)
- TypeScript

**Analysis:**
- Tree-sitter (code parsing)
- JSON Lines (structured data)

## 🚧 Development

### Development Mode
```bash
# Start site in development mode
cd template_site
npm run start

# Build for production
npm run build
npm run serve
```

### Adding New Scanners
1. Add scanning logic to `cli/scanner.py`
2. Update output format in `cli/main.py`
3. Test with `python cli/main.py --repo <test-repo>`

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📜 License

MIT License with Attribution Requirement

Copyright (c) 2025 Akash Bagchi, Akshaya Nadathur, Pranjal Padakannaya, Sachin SS

This project is open source under the MIT License with an attribution requirement.
See [LICENSE](LICENSE) for full details.

**Attribution Requirement:** When using, modifying, or distributing this software,
you must include clear attribution to the original authors and link to this repository.

### How to Attribute

In your documentation, README, or about page, include:
```
Documentation generated using unbored.AI
Created by Akash Bagchi, Akshaya Nadathur, Pranjal Padakannaya, Sachin SS
https://github.com/akashbagchi/unbored.ai
```

## 🎉 Demo

- Pitch Deck: https://www.figma.com/deck/ryyAt60shYMnkMtUzyuecJ/unbored-presentation?node-id=1-32&viewport=-158%2C-121%2C0.72&t=tw2HYoP7KJmOaFKi-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1
- YouTube Demo: https://youtu.be/oMcnYGHypfU

---

*Built during the HackASU 2025 Hackathon hosted by the Claude Builder Club @ ASU*
*"Turn any repository into a self-explaining codebase"*

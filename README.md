# Ghost Onboarder

**Automated onboarding documentation generator that transforms any GitHub repository into a comprehensive documentation site with AI-generated architecture overviews.**

## 🚀 Quick Start

Generate beautiful documentation for any repository in 3 steps:

```bash
# 1. Scan and generate documentation
python generator.py ../path/to/repo username/repo-name

# 2. Start the documentation site
cd ghost-onboarder-site
npm run build
npm run serve

# 3. View at http://localhost:3000
```

> [!WARNING]
> Parts of this README have been generated with the help of LLMs. There may be inconsistencies or errors.
>
> Please post an issue if you find an issue in the documentation

## 🎯 What It Does

Ghost Onboarder automatically creates:

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
ghost-onboarder/
├── cli/                          # Core scanning tools
│   ├── main.py                  # Repository scanner
│   ├── scanner.py               # File analysis logic
│   └── claude_client.py         # Claude API integration
├── generator.py                 # 🔥 Main pipeline script
├── ghost-onboarder-site/        # Docusaurus documentation site
│   ├── docs/intro.md           # Auto-generated architecture overview
│   ├── src/pages/graph.tsx     # Interactive repository graph
│   └── ...
└── outputs/                     # Generated scan results
    ├── scan.jsonl              # Repository analysis
    └── scan.jsonl.graph.json   # Dependency graph data
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm

### Setup
```bash
# Clone repository
git clone <ghost-onboarder-repo>
cd ghost-onboarder

# Install Python dependencies
pip install -r requirements.txt

# Install documentation site dependencies
cd ghost-onboarder-site
npm install
cd ..
```

## 📖 Usage

### Basic Usage

```bash
python generator.py <repo_path> <repo_name> [site_path]
```

**Parameters:**
- `repo_path`: Path to repository to analyze
- `repo_name`: Repository name (e.g., "username/repo-name")
- `site_path`: Documentation site path (default: "ghost-onboarder-site")

**Example:**
```bash
python generator.py ../my-project johndoe/my-project
```

### Advanced Usage

#### Just Generate Scan Data
```bash
python cli/main.py --repo ../my-project --format jsonl --out outputs/scan.jsonl
```

#### Manual Claude API Call
```bash
python cli/claude_client.py outputs/scan.jsonl johndoe/my-project
```

#### Start Documentation Site
```bash
cd ghost-onboarder-site
npm run build
npm run serve
```

## 🔧 Configuration

### Claude API Setup
The pipeline uses a pre-configured AWS Lambda endpoint. No additional API key setup required.

### Customizing the Documentation Site

**Update Site Title/Theme:**
Edit `ghost-onboarder-site/docusaurus.config.ts`

**Add Custom Pages:**
Add files to `ghost-onboarder-site/docs/`

**Modify Graph View:**
Edit `ghost-onboarder-site/src/pages/graph.tsx`

## 📊 Example Output

### Before
```
my-complex-repo/
├── src/
├── components/
├── utils/
├── package.json
└── README.md (minimal)
```

### After
- **📋 Architecture Overview**: "This React application follows a component-based architecture with Redux for state management..."
- **🖼️ Interactive Graph**: Visual nodes showing file relationships
- **🔍 Searchable Docs**: Full-text search across all documentation

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

**Documentation Site:**
- Docusaurus (React-based)
- React Flow (interactive graphs)
- TypeScript

**Analysis:**
- Tree-sitter (code parsing)
- JSON Lines (structured data)

## 🚧 Development

### Running Tests
```bash
python -m pytest tests/
```

### Development Mode
```bash
# Start site in development mode
cd ghost-onboarder-site
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

```bash
🚧 TODO 🚧
```

## 🎉 Demo

- Pitch Deck: https://www.figma.com/deck/ryyAt60shYMnkMtUzyuecJ/unbored-presentation?node-id=7-506&viewport=-158%2C-121%2C0.72&t=tw2HYoP7KJmOaFKi-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1
- YouTube Demo: 

---

*Built during the HackASU 2025 Hackathon hosted by the Claude Builder Club @ ASU*
*"Turn any repository into a self-explaining codebase"*

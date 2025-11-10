---
sidebar_position: 1
---

# akashbagchi/claude-builder-2025 - Architecture Overview

# Ghost Onboarder Developer Documentation

## Understanding the Codebase

Ghost Onboarder follows a hybrid architecture combining a Python-based analysis pipeline with a React-based documentation site. The codebase is structured as two main components:

1. A Python CLI application (`ghost-onboarder/cli/`) that analyzes repositories and generates structured data
2. A Docusaurus site (`ghost-onboarder/ghost-onboarder-site/`) that presents the analysis results

The key architectural pattern is a pipeline where repository data flows through distinct stages: scanning → analysis → AI processing → site generation. This separation allows independent evolution of each stage while maintaining a clear data contract between them using JSONL as the interchange format.

The most important concepts to grasp are:
- The scanner pipeline stages and their data transformations
- How the Claude AI integration enhances the raw scan data
- How the Docusaurus site consumes and visualizes the generated data

## Code Organization & Flow

**cli/**
- **Purpose**: Contains the core repository analysis pipeline and AI integration
- **Key files**:
  - `scanner.py`: The workhorse that walks repository trees and extracts metadata
  - `main.py`: Orchestrates the scanning process and generates JSONL output
  - `claude_client.py`: Handles AI processing via AWS Lambda
- **When you'll touch this**: When modifying how repositories are analyzed or changing the AI prompts
- **Gotchas**: Changes to the JSONL output format in `main.py` require corresponding updates in both `claude_client.py` and the Docusaurus graph visualization

**ghost-onboarder-site/**
- **Purpose**: Presents the analysis results in a searchable, interactive documentation site
- **Key files**:
  - `src/pages/graph.tsx`: Interactive visualization of repository structure
  - `docs/intro.md`: AI-generated architecture overview
  - `docusaurus.config.ts`: Site configuration and theming
- **When you'll touch this**: When modifying how documentation is presented or updating the graph visualization
- **Gotchas**: The graph visualization expects specific JSON schema from `generate_graph_position.py`

**outputs/**
- **Purpose**: Stores intermediate analysis results and final documentation data
- **Key files**:
  - `scan.jsonl`: Raw repository analysis data
  - `scan.jsonl.graph.json`: Processed graph visualization data
- **When you'll touch this**: When debugging pipeline output or modifying data schemas
- **Gotchas**: Files here are overwritten on each run - back up if needed for debugging

## Data Flow Paths

**Repository Analysis Flow**
1. `generator.py` invokes `cli/main.py` to scan the target repository
2. `scanner.py` walks the file tree, extracting metadata into JSONL format
3. `score_repo_files.py` analyzes file importance and relationships
4. `generate_graph_position.py` converts relationships into graph visualization data
5. Output files are written to `outputs/`

**Documentation Generation Flow**
1. `claude_client.py` sends scan data to AWS Lambda for AI processing
2. Lambda returns generated documentation content
3. Content is written to `ghost-onboarder-site/docs/intro.md`
4. Graph data is written to `ghost-onboarder-site/static/graph_with_pos.json`
5. Docusaurus builds the final documentation site

**Graph Visualization Flow**
1. `src/pages/graph.tsx` loads `graph_with_pos.json` on page load
2. React Flow library renders the interactive graph
3. User interactions (zoom, pan, click) are handled by React Flow components
4. Node clicks trigger sidebar updates with file details

## Key Architectural Decisions

**Lambda vs Direct API**
- The project uses AWS Lambda to handle Claude API calls instead of direct integration
- Why? Lambda provides:
  - API key security (not exposed in client code)
  - Request rate limiting and queuing
  - Cost control and monitoring
  - Easier deployment across different environments

**JSONL vs JSON**
- Repository scan data is stored in JSONL (JSON Lines) format
- Why?
  - Streaming-friendly for large repositories
  - Each line is independently parseable
  - Easier to append/modify without loading entire file
  - Better Git diff visibility

**Existing vs Generated Docusaurus**
- The project updates an existing Docusaurus site rather than generating from scratch
- Why?
  - Maintains consistent styling and configuration
  - Preserves custom components and visualizations
  - Allows manual content alongside generated docs
  - Simpler deployment process

**File Scoring System**
- `score_repo_files.py` assigns importance scores to files and directories
- Why?
  - Helps identify key entry points for new developers
  - Prioritizes files for documentation generation
  - Influences graph visualization layout
  - Provides structure for AI analysis

Based on the issue history, new developers should be aware that:
- The JSONL output format is critical - changes require updates in multiple places
- The graph visualization is sensitive to data schema changes
- The CLI commands are being consolidated but some manual steps may still be needed
- Documentation site customization requires understanding both Docusaurus and the generation pipeline

---

*This documentation was automatically generated by Ghost Onboarder using Claude AI.*

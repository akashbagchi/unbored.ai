### 0.6.1

- Features:
  - Improved graph view implementation for more usable information about the codebase

### 0.6.0

- Features:
  - Added support for Go and Rust codebase discovery
  - Added improved signal discovery (key paths, ecosystem detection, test frameworks, etc.)
  - Dark mode toggle added
- Fixes:
  - '0 edge' issue in graph generation -> fixed a off-by-one error preventing proper discovery of graph edges

### 0.5.1

- Features:
  - `unbored view` subcommand -> launches the existing documentation site without running the generation pipeline or making any API calls.
  - Change detection -> saves a git commit snapshot after each full generation run; on subsequent runs, diffs the current HEAD against the stored commit to avoid unnecessary Claude API calls..
    - If the repo is unchanged since last generation, docs launch immediately.
    - If only minor source changes are detected (<=20 lines), user is prompted to choose between regenerating or launching existing docs.

### 0.5.0

- Features:
  - Multi-page module-level documentation
    - Claude outputs a JSON array of page objects instead of a single markdown blob
    - Each major subsystem gits its own page in the docs sidebar (up to 6 pages currently)
  - Dependency versions pinned in `package.json`
- Fixes:
  - Fixed MDX compilation error when claude's response is truncated or wrapped in markdown code fences
  - `max_tokens` increased from 8192 to 16000 to reduce truncation on larger codebases

### 0.4.0

- Features:
  - Direct Anthropic SDK integration, replacing the AWS Lambda proxy
    - Users now provide their own Anthropic API key instead of relying
        on a shared Lambda endpoint.
    - Uses `claude-sonnet-4-20250514` via the `anthropic` Python SDK.
  - Persistent configuration via `~/.unbored/config.yaml`
    - `unbored config set <key> <value>` to store `github_token` and
        `anthropic_api_key`.
    - `unbored config show` displays stored config with masked values.
    - `unbored config clear` wipes all stored config.
  - CLI flags `--api-key` and `--github-token` for per-run token overrides
    - Token resolution priority: CLI flag > environment variable > config file.
  - GitHub PAT support for private repositories
    - Set `github_token` via config or `GITHUB_TOKEN` env var to fetch
        issues from private repos without `--skip_github`.
- Fixes:
  - Removed duplicate `send_to_claude()` call in the CLI pipeline
    - Previously, `cli.py` called `generate_all()` (which calls
        `send_to_claude()` internally) and then called `send_to_claude()`
        again separately.
- Removed:
  - `claude_client.py` — unused standalone client with placeholder Lambda URL.
  - AWS Lambda endpoint dependency in `generator.py`.

### 0.3.0

- Fixes:
  - Added error handling/workarounds for private repos
    - Skip issue discovery if access to remote repository is not
        configured, or if the repository is otherwise not found.

### 0.2.0

- Initial Pre-Release
  - Created installable python package (installable from github with
        `pip install git+https://github.com/akashbagchi/unbored.ai.git@v0.2.0`)
    - Generates one-page documentation for a given codebase using `unbored`
- [Full Release Notes](https://github.com/akashbagchi/unbored.ai/discussions/32)

### 0.1.0

- Initial (Hackathon) version

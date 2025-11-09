# claude-builder-2025

To test the scanner function on a repository:

1. Create a folder called 'tmprepo' in the root directory and clone the repository you want to test there:

    mkdir tmprepo
    cd tmprepo

    Clone a sample repo:

    curl -L https://github.com/akashbagchi/modern-portfolio/archive/refs/heads/main.zip -o repo.zip 
    unzip repo.zip

2. Create a folder 'outputs' in the root directory.

3. The following command reads through the repo and generates the following:
    - scan.md: Provides a human-readable summary of the repo, for user to reference.
    - scan.md.graph.json: JSON graph structure of files in the repository.
    - scan.md.jsonl: JSON file containing key details of files (size, path etc)
    - issues.json: JSON file containing details of last X number of closed issues in the repository.

    ```
    python -m cli.main --repo ../tmprepo/<repo name> --out ../outputs/scan.md --format human --gh-repo <username/reponame> --issues-limit <number of closed issues> --issues-format json --issues-min-hits 1 --issues-out ../outputs/issues.json
    ```

The files are saved in your 'outputs' folder.


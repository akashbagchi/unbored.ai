# claude-builder-2025

To test the scanner function on a repository:

1. Create a folder called 'tmprepo' in the root directory and clone the repository you want to test there:
```
mkdir tmprepo
cd tmprepo

# Clone a sample repo:

curl -L https://github.com/akashbagchi/modern-portfolio/archive/refs/heads/main.zip -o repo.zip
unzip repo.zip
```

2. Create a folder 'outputs' in the root directory.
```
mkdir outputs
```

3. To scan the repo and generate a markdown (human-readable), enter this command after entering the 'ghost-onboarder' folder:
```
python cli/main.py --repo ../tmprepo/<repo-name> --out ../outputs/scan.md
```

4. To scan the repo and generate a jsonl file & graph-relationship file (to feed into claude), enter this command after entering the 'ghost-onboarder' folder:
```
<<<<<<< HEAD
python cli/main.py --repo ../tmprepo/<repo-name> --format jsonl --out ../outputs/scan.jsonl
```
=======
python .\cli\main.py --repo ..\tmprepo\<repo name> --format jsonl --out ..\outputs\scan.jsonl --graph-out ..\outputs\graph.json
```
The files are saved in your 'outputs' folder.
>>>>>>> dev/akshaya

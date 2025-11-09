#!/usr/bin/env python3
import json
import requests
import sys
from pathlib import Path

def send_repo_data(jsonl_file, repo_name=None):
    # Read the JSONL file
    repo_data = Path(jsonl_file).read_text()

    if not repo_name:
        repo_name = "repository"

    payload = {
        "repo_data": repo_data,
        "repo_name": repo_name
    }

    response = requests.post(
        "https://vd03y9yw0g.execute-api.us-east-1.amazonaws.com/prod/chat",
        headers={"Content-Type": "application/json"},
        json=payload
    )

    if response.status_code == 200:
        result = response.json()
        print(result["onboarding_doc"])
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python claude_client.py <jsonl_file> [repo_name]")
        sys.exit(1)

    jsonl_file = sys.argv[1]
    repo_name = sys.argv[2] if len(sys.argv) > 2 else None
    send_repo_data(jsonl_file, repo_name)

#!/usr/bin/env python3
import json
import requests
import sys
from pathlib import Path

def send_repo_data(jsonl_file, repo_name=None):
    # Read the JSONL file
    try:
        repo_data = Path(jsonl_file).read_text()
        print(f"File size: {len(repo_data)} characters")

        # Truncate if too large (Lambda has size limits)
        if len(repo_data) > 100000:  # 100KB limit
            repo_data = repo_data[:100000] + "\n... [TRUNCATED]"
            print("Truncated large file")

    except Exception as e:
        print(f"Error reading file: {e}")
        return

    if not repo_name:
        repo_name = "repository"

    payload = {
        "repo_data": repo_data,
        "repo_name": repo_name
    }

    print(f"Sending payload of size: {len(json.dumps(payload))}")

    try:
        response = requests.post(
            "https://vd03y9yw0g.execute-api.us-east-1.amazonaws.com/prod/chat",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("SUCCESS:")
            print(result.get("onboarding_doc", "No onboarding_doc in response"))
        else:
            print(f"Error: {response.status_code}")
            print("Response:", response.text)

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <jsonl_file> [repo_name]")
        sys.exit(1)

    jsonl_file = sys.argv[1]
    repo_name = sys.argv[2] if len(sys.argv) > 2 else None
    send_repo_data(jsonl_file, repo_name)

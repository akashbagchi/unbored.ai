#!/usr/bin/env python3
import json
import requests

# Test with minimal data
payload = {
    "repo_data": '{"section": "meta", "root": "test"}\n{"section": "ecosystem", "primary": "node"}',
    "repo_name": "test-repo"
}

response = requests.post(
    "https://vd03y9yw0g.execute-api.us-east-1.amazonaws.com/prod/chat",
    headers={"Content-Type": "application/json"},
    json=payload
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

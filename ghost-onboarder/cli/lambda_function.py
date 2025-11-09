"""Calls a public lamba endpoint which is configured to hit Bedrock API configured with our Claude model."""

import json
import boto3
import os

REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

client = boto3.client("bedrock-runtime", region_name=REGION)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        repo_data = body.get("repo_data", "")               # scan .jsonl content
        graph_data = body.get("graph_data", "")            # dependency graph
        issues_data = body.get("issues_data", "")          # GitHub issues
        repo_name = body.get("repo_name", "repository")

        if not repo_data:
            return { "statusCode": 400, "body": "Missing 'repo_data'." }

        prompt = build_comprehensive_prompt(repo_name, repo_data, graph_data, issues_data)

        resp = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
        )

        output = "".join(c.get("text","") for c in resp["output"]["message"]["content"])
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
            },
            "body": json.dumps({
                "architecture_overview": output,
                # Could split into multiple docs (pages) later
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }

def build_comprehensive_prompt(repo_name, repo_data, graph_data, issues_data):
    """Build prompt that incorporates all available data"""

    # Base architecture overview section
    base_prompt = f"""Generate documentation for `{repo_name}` using the data below.

=== ARCHITECTURE OVERVIEW ===
Create a technical overview (1500 words):

1. System Design: Core architecture pattern, layer organization
2. Tech Stack: Primary languages/frameworks and their roles
3. Components: Main modules with specific responsibilities
4. Data Flow: Request/response paths, state management
5. Dependencies: External services/libraries used directly

RULES:
- Focus on implementation details for contributing developers
- Skip basic tech definitions (React, TypeScript, etc.)
- No meta-commentary about this overview
- Only mention explicitly imported/configured libraries
- Technical terminology for 2+ years experience

Repository Structure:
{repo_data}
"""

    # Add dependency graph section if available
    if graph_data:
        base_prompt += f"""

=== MODULE DEPENDENCIES ===
Dependency graph showing import relationships:
{graph_data}

Add a "Module Dependencies" section (200 words) explaining:
- Key dependency clusters (highly connected modules)
- Core vs peripheral modules
- Circular dependencies if any
"""

    # Add issues section if available
    if issues_data:
        base_prompt += f"""

=== KNOWN ISSUES & CONTRIBUTIONS ===
Recent closed issues (setup/config related):
{issues_data}

Create TWO additional sections:

1. "Common Setup Issues" (300 words):
   - Top 3-5 setup problems from issues
   - Brief solutions/workarounds

2. "Contribution Opportunities" (200 words):
   - Patterns in issues suggesting areas needing improvement
   - Good first issues for new contributors
"""

    return base_prompt

# For local testing
if __name__ == "__main__":
    import sys

    # Mock event for testing
    test_event = {
        "body": json.dumps({
            "repo_data": "...",  # Would load from scan.jsonl
            "graph_data": "...",  # Would load from graph.json
            "issues_data": "...",  # Would load from issues.jsonl
            "repo_name": "test/repo"
        })
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))


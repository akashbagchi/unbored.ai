"""Calls a public lambda endpoint which is configured to hit Bedrock API configured with our Claude model."""

import json
import boto3
import os

REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

client = boto3.client("bedrock-runtime", region_name=REGION)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        repo_data = body.get("repo_data", "")
        repo_name = body.get("repo_name", "repository")

        if not repo_data:
            return { "statusCode": 400, "body": "Missing 'repo_data'." }

        prompt = f"""Generate an architectural overview for `{repo_name}`:

                    STRUCTURE (1000-1200 words max)
                    1. System Design: Core architecture pattern, layer organization
                    2. Tech Stack: Primary languages/frameworks and their key roles
                    3. Components: Main modules with specific responsibilities
                    4. Data Flow: Request/response paths, state management
                    5. Dependencies: External services/libraries directly used by developers

                    RULES:
                    - Focus on implementation details developers need to contribute
                    - Skip basic technology definitions (React, TypeScript, etc.)
                    - Omit meta-commentary about this overview
                    - Only mention libraries explicitly imported/configured by developers
                    - Use technical terminology appropriate for 2+ years experience

                    Repository Analysis:
                    {repo_data}"""

        resp = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2500, "temperature": 0.3},
        )

        output = "".join(c.get("text","") for c in resp["output"]["message"]["content"])
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
            },
            "body": json.dumps({"onboarding_doc": output}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }

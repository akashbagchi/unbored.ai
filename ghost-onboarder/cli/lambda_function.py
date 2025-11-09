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

        prompt = f"""You are a senior developer and project lead with 8+ years of experience. Based on the repository `{repo_name}`, Generate a comprehensive overview (1000 words) covering:
                        - High level system design
                        - Tech stack and why it's chosen
                        - Major components/modules and their responsibilities
                        - Data flow between components
                        - External dependencies
                    Write for a developer with 2 years experience.

                    AVOID:
                        - Unnecessary fluff/decorative words singing the praises of certain design decisions, write purely to educate and inform
                        - Unnecessarily verbose explanations that don't capture technical nuance meaningful to a contributing junior developer
                        - Mentioning potential extra uses for certain modules, libraries that aren't used or are only used indirectly (for example by a framework, but not directly chosen by the developer), etc.

                    Repository Analysis:
                    {repo_data} """

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

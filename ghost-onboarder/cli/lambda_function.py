"""Calls a public lambda endpoint which is configured to hit Bedrock API configured with our Claude model."""

import json
import boto3
import os

REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

client = boto3.client("bedrock-runtime", region_name=REGION)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        repo_data = body.get("repo_data", "")
        graph_data = body.get("graph_data", "")
        issues_data = body.get("issues_data", "")
        repo_name = body.get("repo_name", "repository")

        if not repo_data:
            return { "statusCode": 400, "body": "Missing 'repo_data'." }

        prompt = build_comprehensive_prompt(repo_name, repo_data, graph_data, issues_data)

        # ADD DEBUG: Check prompt size
        print(f"Prompt size: {len(prompt)} chars")

        resp = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 8192, "temperature": 0.5},
        )

        # ADD DEBUG: Print full response
        print(f"Full response: {json.dumps(resp, indent=2)}")

        # FIX: Check if response has content
        if "output" not in resp or "message" not in resp["output"]:
            print(f"ERROR: Invalid response structure: {resp}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Invalid API response", "response": str(resp)})
            }

        output = "".join(c.get("text","") for c in resp["output"]["message"]["content"])

        # ADD DEBUG: Check output length
        print(f"Output length: {len(output)} chars")
        print(f"First 500 chars: {output[:500]}")

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
            },
            "body": json.dumps({
                "architecture_overview": output,
            }),
        }
    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }

def build_comprehensive_prompt(repo_name, repo_data, graph_data, issues_data):
    """Build prompt that incorporates all available data"""

    base_prompt = f"""You are writing ONBOARDING DOCUMENTATION for a new developer joining the `{repo_name}` project.

CRITICAL: This is NOT a README. Do NOT include:
- Installation steps
- "How to run" instructions
- Contributing guidelines
- License/demo sections
- Feature lists or "what this project does"

Instead, write for a developer who has ALREADY cloned and run the project, and needs to understand HOW TO WORK IN THIS CODEBASE.

=== REQUIRED STRUCTURE ===

## Understanding the Codebase

[2-3 paragraphs explaining the mental model]
- What architectural pattern drives this project's organization?
- What's the "shape" of the code - monolith, microservices, layered?
- What are the 2-3 most important concepts to grasp?

## Code Organization & Flow

[For each major directory/module, write 1-2 paragraphs answering:]

**[Directory/Module Name]**
- **Purpose in THIS project**: Why does this exist here specifically? What problem does it solve for THIS codebase?
- **Key files and their relationships**: Name 2-4 critical files and explain how they interact
- **When you'll touch this**: What kinds of tasks require modifying these files?
- **Gotchas**: Any non-obvious dependencies or coupling?

Example format:
"The `cli/` directory contains the repository scanning pipeline. `main.py` orchestrates the scan by calling `scanner.py` which walks the file tree and extracts metadata. When adding support for a new file type, you'll modify `scanner.py`'s `process_file()` method AND update the output schema in `main.py`. Note that `claude_client.py` expects the exact JSONL format from `main.py` - changing one requires updating the other."

## Data Flow Paths

[Trace 2-3 concrete scenarios through the codebase]
"When a user runs `generator.py` on a repository:
1. `generator.py` calls `cli/main.py` which returns JSONL to `outputs/scan.jsonl`
2. That JSONL is read and sent to the Lambda endpoint in `claude_client.py`
3. The Lambda response updates `ghost-onboarder-site/docs/intro.md`
4. Docusaurus automatically rebuilds the site"

## Key Architectural Decisions

[Explain WHY things are built this way]
- Why Lambda instead of direct API calls?
- Why JSONL instead of JSON?
- Why update existing Docusaurus vs generate from scratch?

Use this repository structure:
{repo_data}
"""

    if graph_data:
        base_prompt += f"""

## Module Dependency Map

{graph_data}

[150 words explaining the import graph]
- Which modules are central hubs? (imported by many others)
- Which are leaf nodes? (import but aren't imported)
- Any circular dependencies that new devs should know about?
"""

    if issues_data:
        base_prompt += f"""

## Common Pain Points

{issues_data}

[Analyze the closed issues and write:]
- What do new contributors struggle with most?
- What parts of the codebase generate the most confusion?
- What would you warn a new dev about based on these issues?
"""

    base_prompt += """

WRITING RULES:
- Use actual file paths from the repository structure
- Reference specific functions/classes you see in the structure
- Write in second person ("you'll modify X when...")
- Be opinionated about the architecture ("This uses X pattern because...")
- 1500-2000 words total
- NO installation/setup/contributing sections
"""

    return base_prompt

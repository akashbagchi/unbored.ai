'''Calls a public lambda endpoint which is configured to hit Bedrock API configured with our Claude model.'''

import json, boto3, os

REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

client = boto3.client("bedrock-runtime", region_name=REGION)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        msg = body.get("message", "")
        if not msg:
            return {"statusCode": 400, "body": "Missing 'message'."}

        resp = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": msg}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.3},
        )

        output = "".join(c.get("text","") for c in resp["output"]["message"]["content"])
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json",
            },
            "body": json.dumps({"reply": output}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }

import boto3
import json
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Initialize the Bedrock runtime client
client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

# Test different models to see which ones are enabled
test_models = [
    {
        "id": "anthropic.claude-3-haiku-20240307-v1:0",
        "name": "Claude 3 Haiku",
        "format": "claude",
        "body": {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Say hello in one word."}]}],
            "max_tokens": 10,
            "temperature": 0.5
        },
        "extract": lambda r: r["content"][0]["text"]
    },
    {
        "id": "openai.gpt-oss-20b-1:0",
        "name": "OpenAI GPT OSS 20B",
        "format": "openai",
        "body": {
            "messages": [{"role": "user", "content": "Say hello in one word."}],
            "max_tokens": 10,
            "temperature": 0.5
        },
        "extract": lambda r: r["choices"][0]["message"]["content"]
    },
    {
        "id": "meta.llama3-8b-instruct-v1:0",
        "name": "Meta Llama 3 8B",
        "format": "llama",
        "body": {
            "prompt": "\n<|begin_of_text|><|start_header_id|>user<|end_header_id|>\nSay hello in one word.\n<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n",
            "max_gen_len": 10,
            "temperature": 0.5
        },
        "extract": lambda r: r["generation"]
    }
]

print("Testing which models are enabled in your AWS Bedrock account...\n")
print("=" * 60)

enabled_models = []

for model in test_models:
    try:
        print(f"\nTesting: {model['name']} ({model['id']})...")
        response = client.invoke_model(
            modelId=model["id"],
            body=json.dumps(model["body"])
        )
        response_body = json.loads(response["body"].read())
        result = model["extract"](response_body)
        print(f"✅ SUCCESS! Response: {result}")
        enabled_models.append(model)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ValidationException":
            print(f"❌ Not enabled (Operation not allowed)")
        else:
            print(f"❌ Error: {error_code}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

print("\n" + "=" * 60)
print(f"\nSummary: {len(enabled_models)} out of {len(test_models)} models are enabled")
if enabled_models:
    print("\n✅ Enabled models:")
    for model in enabled_models:
        print(f"   - {model['name']} ({model['id']})")
else:
    print("\n⚠️  No models are enabled. Please enable models in the AWS Bedrock Console:")
    print("   https://console.aws.amazon.com/bedrock/ → Model access")


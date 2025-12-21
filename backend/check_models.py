import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Use the control-plane Bedrock client to list models
bedrock_client = boto3.client("bedrock", region_name=os.getenv("AWS_REGION", "us-east-1"))

print("Checking Meta Llama models in us-east-1...\n")

response = bedrock_client.list_foundation_models()

# Filter for Meta Llama models
meta_models = [
    model for model in response["modelSummaries"]
    if model["providerName"] == "Meta" and "llama" in model["modelId"].lower()
]

print(f"Found {len(meta_models)} Meta Llama models:\n")
for model in meta_models:
    print(f"  Model ID: {model['modelId']}")
    print(f"  Name: {model['modelName']}")
    print(f"  Inference Types: {model['inferenceTypesSupported']}")
    print(f"  Status: {model['modelLifecycle']['status']}")
    print()

print("\n" + "="*60)
print("NOTE: Even if models are listed above, you may need to")
print("enable them in the AWS Bedrock Console:")
print("1. Go to: https://console.aws.amazon.com/bedrock/")
print("2. Navigate to 'Model access' in the left sidebar")
print("3. Find the Meta Llama models and click 'Enable'")
print("4. Wait a few minutes for the models to be enabled")
print("="*60)




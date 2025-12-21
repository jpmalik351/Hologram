import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()   

# Make sure you're using the runtime client for Bedrock
client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))

# Use the control-plane Bedrock client to list models
bedrock_client = boto3.client("bedrock", region_name=os.getenv("AWS_REGION"))

response = bedrock_client.list_foundation_models()
print(json.dumps(response, indent=2))
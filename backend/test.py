import boto3
import json
import os

from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Initialize the Bedrock runtime client (region from env, default to us-east-1)
client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

model_id = "openai.gpt-oss-20b-1:0"

# Define the prompt for the model.
prompt = "Describe the purpose of a 'hello world' program in one line."

# Format the request payload for OpenAI models in Bedrock (chat format)
native_request = {
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "max_tokens": 512,
    "temperature": 0.5,
}

# Convert the native request to JSON.
request = json.dumps(native_request)

try:
    print(f"Calling Bedrock model: {model_id}")
    print(f"Region: {os.getenv('AWS_REGION', 'us-east-1')}")
    print(f"Request: {request}\n")

    # Invoke the model with the request.
    response = client.invoke_model(modelId=model_id, body=request)

except (ClientError, Exception) as e:
    print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
    raise

# Decode the response body.
model_response = json.loads(response["body"].read())

# Extract and print the response text (OpenAI format)
response_text = model_response["choices"][0]["message"]["content"]

print("✅ Success! Response from Bedrock (OpenAI GPT OSS):")
print("-" * 50)
print(response_text)
print("-" * 50)

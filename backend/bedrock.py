import boto3
import json
import os

client = boto3.client("bedrock-runtime",
                      region_name=os.getenv("AWS_REGION")
)

#model_id = os.getenv("MODEL_ID")
model_id = "anthropic.claude-3-haiku-20240307-v1:0"


def call_llm(user_message: str, conversation_history: list[str]) -> str:
    '''
    Call the LLM with the given message and conversation history.
    '''
    messages = []
    
    for msg in conversation_history:
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": msg}]
        })
    
    messages.append({
        "role": "user",
        "content": [{"type": "text", "text": user_message}]
    })

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "max_tokens": 100,
        "temperature": 0.7
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]
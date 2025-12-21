import boto3, json, os
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    "bedrock-runtime",
    region_name="us-west-2"
)

def chat(message: str, conversation_history: list[str]):
    next_message = ""
    if message == "Hello" and conversation_history == []:
        next_message = "Hello, nice to meet you!"
    elif message == "Hello" and conversation_history != []:
        next_message = "Hi you're back!"
    else:
        next_message = "I'm sorry, I don't understand. Please try again."
    
    conversation_history.append(next_message)
    return conversation_history
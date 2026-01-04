# How to Enable Models in AWS Bedrock

## Quick Steps:

1. **Go to AWS Bedrock Console**
   - URL: https://console.aws.amazon.com/bedrock/
   - Make sure you're in the **us-east-1** region (check top-right corner)

2. **Navigate to Model Access**
   - Click on **"Model access"** in the left sidebar
   - Or go directly to: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess

3. **Enable Models**
   - Find the models you want to use:
     - **OpenAI GPT OSS 20B** (`openai.gpt-oss-20b-1:0`)
     - **Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`)
     - **Meta Llama 3 8B** (`meta.llama3-8b-instruct-v1:0`)
   - Click the **"Enable"** button next to each model
   - Wait a few minutes for activation

4. **Verify**
   - After enabling, run: `python test_models.py`
   - This will test which models are now working

## Alternative: Use AWS CLI

If you prefer command line, you can also enable models using AWS CLI:

```bash
# Enable OpenAI GPT OSS 20B
aws bedrock put-model-invocation-logging-configuration \
  --region us-east-1 \
  --logging-config '{"textDataDeliveryEnabled":true}'

# Or use the Bedrock console - it's easier!
```

## Note

- Model access is **free to enable** (you only pay for usage)
- Some models may require approval or have usage limits
- Changes can take a few minutes to propagate









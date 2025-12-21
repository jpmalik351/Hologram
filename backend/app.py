from flask import Flask, request, jsonify
from flask_cors import CORS
from bedrock import call_llm
import boto3
import json
import os
import tempfile

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

conversation_history = []

@app.route('/chat', methods=['POST'])
def chat():
    global conversation_history

    data = request.json
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    if user_message == "Hello" and not conversation_history:
        reply = "Hello, nice to meet you!"
    elif user_message == "Exit":
        conversation_history = []
        return jsonify({'response': "Goodbye!"})
    else:
        reply = call_llm(user_message, conversation_history)
    
    conversation_history.append(reply)
    conversation_history = conversation_history[-10:]
    return jsonify({'response': reply})

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Transcribe audio file to text using AWS Transcribe Streaming
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
        audio_file.save(tmp_file.name)
        tmp_path = tmp_file.name
    
    try:
        # Use AWS Transcribe Streaming API
        transcribe_streaming = boto3.client(
            'transcribe-streaming',
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        
        # Read audio file
        with open(tmp_path, 'rb') as f:
            audio_data = f.read()
        
        # Transcribe Streaming requires PCM audio format
        # For webm/opus, we need to convert or use a different approach
        # Let's use the synchronous Transcribe API with S3 instead
        
        # For now, let's use a simpler approach: synchronous transcribe with S3
        transcribe_client = boto3.client(
            'transcribe',
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        
        s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "us-east-1"))
        bucket_name = os.getenv("S3_BUCKET_NAME")
        
        if not bucket_name:
            # Fallback: try to use a default bucket or create one
            # For MVP, let's return a helpful error
            os.unlink(tmp_path)
            return jsonify({
                'error': 'S3_BUCKET_NAME environment variable not set. Please configure an S3 bucket for transcription.'
            }), 500
        
        # Upload to S3
        import uuid
        s3_key = f"audio/{uuid.uuid4()}.webm"
        try:
            s3_client.upload_file(tmp_path, bucket_name, s3_key)
        except Exception as e:
            os.unlink(tmp_path)
            return jsonify({'error': f'Failed to upload to S3: {str(e)}'}), 500
        
        # Start transcription job
        job_name = f"transcribe-{uuid.uuid4()}"
        try:
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': f's3://{bucket_name}/{s3_key}'},
                MediaFormat='webm',
                LanguageCode='en-US'
            )
        except Exception as e:
            # Clean up
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
            except:
                pass
            os.unlink(tmp_path)
            return jsonify({'error': f'Failed to start transcription: {str(e)}'}), 500
        
        # Wait for job to complete (with timeout)
        import time
        max_wait = 60  # 60 seconds max
        elapsed = 0
        job_status = None
        status = None
        
        while elapsed < max_wait:
            try:
                status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
                job_status = status['TranscriptionJob']['TranscriptionJobStatus']
                if job_status in ['COMPLETED', 'FAILED']:
                    break
            except Exception as e:
                break
            time.sleep(2)
            elapsed += 2
        
        # Clean up S3 file
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        except:
            pass
        
        # Clean up transcription job
        try:
            transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
        except:
            pass
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        if elapsed >= max_wait or job_status is None:
            return jsonify({'error': 'Transcription timeout'}), 500
        
        if job_status == 'FAILED':
            failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown error') if status else 'Unknown error'
            return jsonify({'error': f'Transcription failed: {failure_reason}'}), 500
        
        # Get transcription result
        transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        import urllib.request
        with urllib.request.urlopen(transcript_uri) as response:
            transcript_data = json.loads(response.read())
        
        transcript_text = transcript_data['results']['transcripts'][0]['transcript']
        
        return jsonify({'text': transcript_text})
        
    except Exception as e:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
import boto3
import time
import urllib.request
import json
import os
import sys

# CONFIGURATION
BUCKET_NAME = 'fernando-transcribe-app-2025'
REGION = 'us-east-2'
TRANSCRIPT_FOLDER = 'transcripts'  # <--- New folder name

def transcribe_video(file_path):
    # 1. Setup
    s3 = boto3.client('s3', region_name=REGION)
    transcribe = boto3.client('transcribe', region_name=REGION)
    
    file_name = os.path.basename(file_path)
    # Sanitize filename for AWS (no spaces/dots in job name)
    safe_name = file_name.replace(" ", "_").replace(".", "_")
    job_name = f"job-{safe_name}-{int(time.time())}"
    s3_uri = f"s3://{BUCKET_NAME}/{file_name}"

    # 2. Upload
    print(f"--- Processing: {file_name} ---")
    print(f"Uploading to S3 ({REGION})...")
    s3.upload_file(file_path, BUCKET_NAME, file_name)

    # 3. Start Job
    print(f"Starting Transcription Job: {job_name}")
    try:
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': s3_uri},
            MediaFormat='mp4', 
            LanguageCode='en-US'
        )
    except Exception as e:
        print(f"Error starting job: {e}")
        return

    # 4. Wait
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status['TranscriptionJob']['TranscriptionJobStatus']
        
        if job_status in ['COMPLETED', 'FAILED']:
            break
        print("Status: IN_PROGRESS... (checking again in 5s)")
        time.sleep(5)

    # 5. Save Result to Folder
    if job_status == 'COMPLETED':
        transcript_url = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        response = urllib.request.urlopen(transcript_url)
        data = json.loads(response.read())
        
        text = data['results']['transcripts'][0]['transcript']
        
        # Create folder if it doesn't exist
        if not os.path.exists(TRANSCRIPT_FOLDER):
            os.makedirs(TRANSCRIPT_FOLDER)
            
        # Save to transcripts/filename.txt
        output_file = os.path.join(TRANSCRIPT_FOLDER, file_name + ".txt")
        
        with open(output_file, "w") as f:
            f.write(text)
            
        print(f"\nSUCCESS! Transcript saved to: {output_file}")
    else:
        print("Transcription Failed.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        transcribe_video(video_file)
    else:
        print("Usage: python3 transcribe.py <video_file>")
import boto3
import time
import urllib.request
import json
import os
import argparse

# CONFIGURATION
BUCKET_NAME = 'fernando-transcribe-app-2025'
REGION = 'us-east-2'
TRANSCRIPT_FOLDER = 'transcripts'

def transcribe_video(file_path, language_code, multi_mode):
    # 0. Prepare Folders
    if not os.path.exists(TRANSCRIPT_FOLDER):
        os.makedirs(TRANSCRIPT_FOLDER)

    # 1. Setup AWS
    s3 = boto3.client('s3', region_name=REGION)
    transcribe = boto3.client('transcribe', region_name=REGION)
    
    file_name = os.path.basename(file_path)
    safe_name = file_name.replace(" ", "_").replace(".", "_")
    job_name = f"job-{safe_name}-{int(time.time())}"
    s3_uri = f"s3://{BUCKET_NAME}/{file_name}"

    # 2. Upload
    print(f"--- Processing: {file_name} ---")
    print(f"Uploading to S3 ({REGION})...")
    s3.upload_file(file_path, BUCKET_NAME, file_name)

    # 3. Configure Job Settings
    job_args = {
        'TranscriptionJobName': job_name,
        'Media': {'MediaFileUri': s3_uri},
        'MediaFormat': 'mp4',
    }

    if multi_mode:
        print(f"Starting Job: MULTI-LANGUAGE (EN, ES, PT)")
        job_args['IdentifyMultipleLanguages'] = True
        job_args['LanguageOptions'] = ['en-US', 'es-US', 'pt-BR']
        job_args['Settings'] = {'ShowSpeakerLabels': False}
    else:
        print(f"Starting Job: SINGLE LANGUAGE ({language_code}) with Speaker ID")
        job_args['LanguageCode'] = language_code
        job_args['Settings'] = {'ShowSpeakerLabels': True, 'MaxSpeakerLabels': 10}

    # 4. Start Job
    try:
        transcribe.start_transcription_job(**job_args)
    except Exception as e:
        print(f"Error starting job: {e}")
        return

    # 5. Wait
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status['TranscriptionJob']['TranscriptionJobStatus']
        
        if job_status in ['COMPLETED', 'FAILED']:
            break
        print("Status: IN_PROGRESS... (checking again in 5s)")
        time.sleep(5)

    # 6. Process Results
    if job_status == 'COMPLETED':
        transcript_url = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        response = urllib.request.urlopen(transcript_url)
        data = json.loads(response.read())
        
        final_text = ""
        results = data.get('results', {})
        
        # Safe check: Do we have speaker labels?
        labels = results.get('speaker_labels')
        
        # We only try to use labels if they exist AND are not None
        if labels is not None and 'segments' in labels:
            segments = labels['segments']
            items = results.get('items', [])
            word_map = {item['start_time']: item['alternatives'][0]['content'] 
                       for item in items if 'start_time' in item}

            for segment in segments:
                speaker = segment['speaker_label']
                segment_words = []
                for item in segment['items']:
                    if item['start_time'] in word_map:
                        segment_words.append(word_map[item['start_time']])
                final_text += f"{speaker}: {' '.join(segment_words)}\n"
        
        else:
            # Fallback: Just grab the plain text if speaker detection failed or wasn't requested
            if 'transcripts' in results and len(results['transcripts']) > 0:
                final_text = results['transcripts'][0]['transcript']
            else:
                final_text = "[Error: No transcript text found]"
        
        # --- NEW NAMING LOGIC ---
        base_name = file_name + ".txt"
        output_file = os.path.join(TRANSCRIPT_FOLDER, base_name)
        
        counter = 2
        while os.path.exists(output_file):
            output_file = os.path.join(TRANSCRIPT_FOLDER, f"{file_name} ({counter}).txt")
            counter += 1
        # ------------------------

        with open(output_file, "w") as f:
            f.write(final_text)
            
        print(f"\nSUCCESS! Transcript saved to: {output_file}")
        
        # 7. Delete from S3
        print(f"Cleaning up: Deleting {file_name} from S3...")
        s3.delete_object(Bucket=BUCKET_NAME, Key=file_name)
        print("Done.")
    else:
        print("Transcription Failed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Video Transcriber")
    parser.add_argument("file", help="Path to video file")
    parser.add_argument("--lang", default="en-US", help="Language code (e.g., pt-BR). Default: en-US")
    parser.add_argument("--multi", action="store_true", help="Enable multi-language detection")
    
    args = parser.parse_args()
    
    transcribe_video(args.file, args.lang, args.multi)
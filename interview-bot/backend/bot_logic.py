import os
import torch
import whisperx
import openai
import json
import subprocess
import shlex
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
AI_MODEL = "gpt-3.5-turbo"

WHISPER_MODEL = "base"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# The path to your new, energetic 'hfc_female' voice model
VOICE_MODEL_PATH = 'en_US-hfc_female-medium.onnx'

system_prompt = (
    "You are a highly skilled interviewer for the Malaysian Student Initiative (MSI). Your persona is professional, warm, and insightful. Your main goal is to conduct a realistic and interactive mock scholarship interview. "
    "Your core behavior is '点到为止' (diǎn dào wéi zhǐ) - be interactive but always maintain control. "
    "You MAY answer simple, clarifying questions about the interview process, but you MUST deflect personal or opinion-based questions, always pivoting the focus back to the candidate. "
    "For example, if asked for your opinion, say 'That's an interesting question. For this interview, my focus is on understanding your perspective. What is it about that topic that you find compelling?' "
    "Your goal is to assess the candidate's background, chosen field, leadership, and character by asking probing follow-up questions to short answers and moving on after clear, detailed answers."
)

# --- Initialize Models ---
print("Loading WhisperX model...")
whisper_model = whisperx.load_model(WHISPER_MODEL, DEVICE, compute_type=COMPUTE_TYPE)
print("WhisperX model loaded.")

print(f"Piper TTS voice model '{VOICE_MODEL_PATH}' is ready to be used via command line.")

# --- Core Functions ---
def transcribe_audio_with_whisperx(audio_path):
    print("Transcribing audio...")
    audio = whisperx.load_audio(audio_path)
    result = whisper_model.transcribe(audio, batch_size=4, language="en")
    transcribed_text = " ".join([segment['text'] for segment in result['segments']])
    if transcribed_text.lower().strip() in ["you", "thank you.", "thanks for watching."]:
        return ""
    print(f"You said: {transcribed_text}")
    return transcribed_text.strip()

# --- THE DEFINITIVE AUDIO GENERATION FUNCTION ---
def generate_audio_via_cmd(text: str, output_path_mp3: str) -> str:
    """
    Generates audio by piping piper.exe directly into ffmpeg.exe.
    This is the most stable method, bypassing all Python library conflicts.
    """
    print("Generating audio via direct command-line pipe...")
    
    piper_command = [
        'piper',
        '--model', VOICE_MODEL_PATH,
        '--output-raw'
    ]

    ffmpeg_command = [
        'ffmpeg',
        '-f', 's16le', '-ar', '22050', '-ac', '1', '-i', 'pipe:0',
        '-y', '-b:a', '192k', output_path_mp3
    ]

    # --- THIS IS THE FIX ---
    # We must explicitly create a pipe for stdin to write to.
    piper_process = subprocess.Popen(piper_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=piper_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Pass the text to piper's stdin, which now exists, and close it.
    piper_process.stdin.write(text.encode('utf-8'))
    piper_process.stdin.close()
    
    piper_process.wait()
    ffmpeg_process.wait()

    if ffmpeg_process.returncode != 0:
        print("!!!!!! FFMPEG COMMAND FAILED !!!!!!")
        print(f"FFmpeg stderr: {ffmpeg_process.stderr.decode()}")
        raise Exception("FFmpeg failed to convert audio.")
    else:
        print(f"Successfully generated {output_path_mp3}")
        
    return output_path_mp3
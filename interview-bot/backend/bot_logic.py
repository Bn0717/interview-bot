# backend/bot_logic.py

import os
import torch
import whisperx
import openai
import subprocess
from dotenv import load_dotenv

# --- Environment and API Setup ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
AI_MODEL = "gpt-3.5-turbo"

# --- Model Configuration ---
WHISPER_MODEL_NAME = "base"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# --- PATHS FOR RENDER DEPLOYMENT ---
PIPER_EXECUTABLE_PATH = './piper/piper' 
VOICE_MODEL_PATH = 'en_US-hfc_female-medium.onnx'

# --- LAZY LOADING IMPLEMENTATION ---
# We start with the model as None. It will be loaded only when needed.
whisper_model = None

def load_whisper_model_if_needed():
    """
    This function checks if the WhisperX model is loaded.
    If not, it loads it into memory. This happens only once.
    """
    global whisper_model
    if whisper_model is None:
        print("WhisperX model is not loaded. Loading now... (This may take a moment)")
        try:
            whisper_model = whisperx.load_model(WHISPER_MODEL_NAME, DEVICE, compute_type=COMPUTE_TYPE)
            print("WhisperX model loaded successfully.")
        except Exception as e:
            print(f"FATAL: Could not load WhisperX model. Error: {e}")
            # If the model fails to load, we should raise an exception
            # to prevent the app from running in a broken state.
            raise e

# --- System Prompt for the AI ---
system_prompt = (
    "You are a highly skilled interviewer for the Malaysian Student Initiative (MSI). Your persona is professional, warm, and insightful. Your main goal is to conduct a realistic and interactive mock scholarship interview. "
    "Your core behavior is '点到为止' (diǎn dào wéi zhǐ) - be interactive but always maintain control. "
    "You MAY answer simple, clarifying questions about the interview process, but you MUST deflect personal or opinion-based questions, always pivoting the focus back to the candidate. "
    "For example, if asked for your opinion, say 'That's an interesting question. For this interview, my focus is on understanding your perspective. What is it about that topic that you find compelling?' "
    "Your goal is to assess the candidate's background, chosen field, leadership, and character by asking probing follow-up questions to short answers and moving on after clear, detailed answers."
)


# --- Core Logic Functions ---

def transcribe_audio_with_whisperx(audio_path: str) -> str:
    """
    Transcribes the given audio file using the WhisperX model.
    It will trigger the model to load on the very first call.
    """
    # This is the key change: ensure the model is loaded before using it.
    load_whisper_model_if_needed()

    print(f"Transcribing audio from: {audio_path}")
    try:
        audio = whisperx.load_audio(audio_path)
        result = whisper_model.transcribe(audio, batch_size=4, language="en")
        transcribed_text = " ".join([segment.get('text', '') for segment in result.get('segments', [])])
        
        if transcribed_text.lower().strip() in ["you", "thank you.", "thanks for watching."]:
            return ""
            
        print(f"Transcription result: '{transcribed_text}'")
        return transcribed_text.strip()
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""


def generate_audio_via_cmd(text: str, output_path_mp3: str) -> str:
    """
    Generates speech audio by piping the Piper executable's raw output to FFmpeg for MP3 conversion.
    """
    print(f"Generating audio for text: '{text[:50]}...'")
    
    piper_command = [PIPER_EXECUTABLE_PATH, '--model', VOICE_MODEL_PATH, '--output-raw']
    ffmpeg_command = ['ffmpeg', '-f', 's16le', '-ar', '22050', '-ac', '1', '-i', 'pipe:0', '-y', '-q:a', '0', output_path_mp3]

    try:
        piper_process = subprocess.Popen(piper_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=piper_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        piper_process.stdin.write(text.encode('utf-8'))
        piper_process.stdin.close()
        _, ffmpeg_err = ffmpeg_process.communicate()

        if ffmpeg_process.returncode != 0:
            print(f"!!!!!! FFMPEG COMMAND FAILED !!!!!!\nFFmpeg stderr: {ffmpeg_err.decode()}")
            raise Exception("FFmpeg failed to convert audio.")
        else:
            print(f"Successfully generated audio at: {output_path_mp3}")

    except FileNotFoundError:
        print(f"FATAL ERROR: 'ffmpeg' or 'piper' executable not found. Ensure '{PIPER_EXECUTABLE_PATH}' exists.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during audio generation: {e}")
        raise
        
    return output_path_mp3
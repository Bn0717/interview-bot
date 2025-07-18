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
WHISPER_MODEL = "base"
# On Render's CPU instances, this will correctly default to "cpu" and "int8"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# --- PATHS FOR RENDER DEPLOYMENT ---
# These paths MUST match the files downloaded by the build.sh script.

# The build.sh script downloads the Piper executable into a 'piper' subdirectory.
PIPER_EXECUTABLE_PATH = './piper/piper' 

# The build.sh script downloads the voice model to the root of the backend directory.
VOICE_MODEL_PATH = 'en_US-hfc_female-medium.onnx'

# --- System Prompt for the AI ---
system_prompt = (
    "You are a highly skilled interviewer for the Malaysian Student Initiative (MSI). Your persona is professional, warm, and insightful. Your main goal is to conduct a realistic and interactive mock scholarship interview. "
    "Your core behavior is '点到为止' (diǎn dào wéi zhǐ) - be interactive but always maintain control. "
    "You MAY answer simple, clarifying questions about the interview process, but you MUST deflect personal or opinion-based questions, always pivoting the focus back to the candidate. "
    "For example, if asked for your opinion, say 'That's an interesting question. For this interview, my focus is on understanding your perspective. What is it about that topic that you find compelling?' "
    "Your goal is to assess the candidate's background, chosen field, leadership, and character by asking probing follow-up questions to short answers and moving on after clear, detailed answers."
)


# --- Initialize Models on Startup ---
# This code runs only once when the server starts, which is efficient.
print("Loading WhisperX model...")
try:
    whisper_model = whisperx.load_model(WHISPER_MODEL, DEVICE, compute_type=COMPUTE_TYPE)
    print("WhisperX model loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load WhisperX model. Error: {e}")

print(f"Piper TTS voice model '{VOICE_MODEL_PATH}' is ready to be used via command line.")
if not os.path.exists(PIPER_EXECUTABLE_PATH):
    print(f"WARNING: Piper executable not found at '{PIPER_EXECUTABLE_PATH}'. The build.sh script may not have run correctly.")
if not os.path.exists(VOICE_MODEL_PATH):
    print(f"WARNING: Piper voice model not found at '{VOICE_MODEL_PATH}'. The build.sh script may not have run correctly.")


# --- Core Logic Functions ---

def transcribe_audio_with_whisperx(audio_path: str) -> str:
    """
    Transcribes the given audio file using the pre-loaded WhisperX model.
    """
    print(f"Transcribing audio from: {audio_path}")
    try:
        audio = whisperx.load_audio(audio_path)
        result = whisper_model.transcribe(audio, batch_size=4, language="en")
        # Joining text segments to form the full transcription
        transcribed_text = " ".join([segment.get('text', '') for segment in result.get('segments', [])])
        
        # Simple filter for common junk transcriptions from silence or background noise
        if transcribed_text.lower().strip() in ["you", "thank you.", "thanks for watching."]:
            return ""
            
        print(f"Transcription result: '{transcribed_text}'")
        return transcribed_text.strip()
    except Exception as e:
        print(f"Error during transcription: {e}")
        return "" # Return empty string on error


def generate_audio_via_cmd(text: str, output_path_mp3: str) -> str:
    """
    Generates speech audio by piping the Piper executable's raw output to FFmpeg for MP3 conversion.
    This method is robust and works well in containerized environments like Render.
    """
    print(f"Generating audio for text: '{text[:50]}...'")
    
    # Command to run the Piper executable
    piper_command = [
        PIPER_EXECUTABLE_PATH,
        '--model', VOICE_MODEL_PATH,
        '--output-raw'  # Output raw audio data to stdout
    ]

    # Command to run FFmpeg, taking raw audio from stdin
    ffmpeg_command = [
        'ffmpeg',
        '-f', 's16le',      # Input format: 16-bit signed little-endian PCM
        '-ar', '22050',     # Input sample rate (must match the Piper model)
        '-ac', '1',         # Input audio channels (mono)
        '-i', 'pipe:0',     # Input from stdin (the pipe)
        '-y',               # Overwrite output file if it exists
        '-q:a', '0',        # Use VBR for high-quality MP3 encoding
        output_path_mp3
    ]

    try:
        # Start the Piper process
        piper_process = subprocess.Popen(piper_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Start the FFmpeg process, piping Piper's output to its input
        ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=piper_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Pass the text to Piper's stdin and close it to signal end of input.
        # This is more robust than separate wait calls. It writes data and waits for completion.
        piper_process.stdin.write(text.encode('utf-8'))
        piper_process.stdin.close()

        # Wait for FFmpeg to finish and capture any error output
        _, ffmpeg_err = ffmpeg_process.communicate()

        # Check if FFmpeg encountered an error
        if ffmpeg_process.returncode != 0:
            print("!!!!!! FFMPEG COMMAND FAILED !!!!!!")
            print(f"FFmpeg stderr: {ffmpeg_err.decode()}")
            # It's also helpful to see if Piper had an error
            _, piper_err = piper_process.communicate()
            print(f"Piper stderr: {piper_err.decode()}")
            raise Exception("FFmpeg failed to convert audio.")
        else:
            print(f"Successfully generated audio at: {output_path_mp3}")

    except FileNotFoundError:
        print("FATAL ERROR: 'ffmpeg' or 'piper' executable not found.")
        print(f"Ensure '{PIPER_EXECUTABLE_PATH}' exists and 'ffmpeg' is installed via build.sh.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during audio generation: {e}")
        raise
        
    return output_path_mp3
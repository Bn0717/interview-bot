#!/usr/bin/env bash
# exit on error
set -e

# 1. Install System Dependencies
echo "Installing system dependencies: ffmpeg and wget..."
apt-get update && apt-get install -y ffmpeg wget

# 2. Download the Piper TTS Executable
echo "Downloading Piper TTS executable..."
# This link is for a recent Linux x86_64 build. Check for newer versions if needed.
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz
tar -xzvf piper_linux_x86_64.tar.gz
# The executable will now be at ./piper/piper

# 3. Download Your Voice Model
echo "Downloading Piper TTS voice model..."
# Replace with the correct URL for your hfc_female model if it's hosted elsewhere
# This is a common high-quality female voice from Hugging Face
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx

# 4. Install Python Dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo "Build complete."
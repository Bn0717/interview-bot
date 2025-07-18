#!/usr/bin/env bash
# exit on error
set -e

# 1. Install System Dependencies (FIXED)
echo "Installing system dependencies: ffmpeg and wget..."
apt-get clean && apt-get update && apt-get install -y ffmpeg wget

# 2. Download the Piper TTS Executable (FIXED URL)
echo "Downloading Piper TTS executable..."
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
tar -xzvf piper_linux_x86_64.tar.gz

# 3. Download Your Voice Model
echo "Downloading Piper TTS voice model..."
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx

# 4. Install Python Dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo "Build complete."
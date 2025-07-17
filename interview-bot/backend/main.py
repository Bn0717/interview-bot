import os
import json
import openai
from fastapi import FastAPI, File, UploadFile, Form, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import time

from bot_logic import (
    transcribe_audio_with_whisperx,
    generate_audio_via_cmd,
    system_prompt,
    AI_MODEL
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-Data", "X-Feedback-Text"]
)

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

JUNK_TEXTS = {"", "you", "thanks for watching", "thank you for watching", "bye", "thank you"}

def audio_streamer(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            yield from audio_file
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/start_interview")
async def start_interview():
    initial_text = (
        "Hello! Welcome to the mock interview session with the Malaysian Student Initiative. "
        "To begin, could you please tell me a little bit about yourself and what field of study you are planning to pursue?"
    )
    output_path_mp3 = os.path.join(TEMP_DIR, f"temp_audio_{time.time()}.mp3")
    generate_audio_via_cmd(initial_text, output_path_mp3)
    return StreamingResponse(audio_streamer(output_path_mp3), media_type="audio/mpeg")

@app.post("/interview_turn")
async def handle_interview_turn(audio: UploadFile = File(...), history_json: str = Form(...)):
    history = json.loads(history_json)
    messages_for_api = [{"role": "system", "content": system_prompt}] + history
    messages_for_api.append({"role": "user", "content": ""}) 
    
    user_audio_path = os.path.join(TEMP_DIR, f"user_answer_{time.time()}.wav")
    with open(user_audio_path, "wb") as f:
        f.write(await audio.read())

    user_text = transcribe_audio_with_whisperx(user_audio_path)
    os.remove(user_audio_path)

    if not user_text or user_text.lower() in JUNK_TEXTS:
        ai_text = "I'm sorry, I couldn't hear you clearly. Could you please repeat that?"
        updated_history = history
    else:
        messages_for_api[-1]['content'] = user_text
        response = openai.chat.completions.create(model=AI_MODEL, messages=messages_for_api, temperature=0.7)
        ai_text = response.choices[0].message.content
        updated_history = history + [{"role": "user", "content": user_text}, {"role": "assistant", "content": ai_text}]
    
    output_path_mp3 = os.path.join(TEMP_DIR, f"temp_audio_{time.time()}.mp3")
    generate_audio_via_cmd(ai_text, output_path_mp3)

    conversation_data = { "user_text": user_text, "ai_text": ai_text, "history": updated_history }
    
    return StreamingResponse(
        audio_streamer(output_path_mp3), 
        media_type="audio/mpeg",
        headers={"X-Conversation-Data": json.dumps(conversation_data)}
    )

@app.post("/end_interview_summary")
async def end_interview_summary(history: list = Body(...)):
    print(">>> Generating final interview summary...")
    
    user_turns = [msg for msg in history if msg['role'] == 'user']
    if len(user_turns) < 1:
        feedback_text = "It seems the interview ended before you had a chance to answer. Please try again to get personalized feedback. Best of luck!"
    else:
        summary_system_prompt = (
            "You are a professional interview coach delivering a final verbal debrief. Speak like a real human coach: honest, direct, and helpful — not robotic or overly polished. "
            "Avoid markdown formatting, headings, or asterisks. Keep it conversational, clear, and grounded. "
            
            "Your feedback must be 100% based on the actual transcript. Do not make up or assume strengths that are not demonstrated. "
            "If the candidate didn’t answer a question, repeat themselves, or gave irrelevant responses, you must call that out clearly and reflect it in the score. "
            
            "Here’s how to structure your feedback: "
            
            "1. Start with the score using this exact format: 'Your overall score is [number] marks.' or 'I'd score that interview a [number] marks.' "
            "For example, say 'Your overall score is thirty-five marks.' Do not say 'slash' or 'over one hundred'."
            
            "2. Then give your honest analysis: "
            "- For strengths: Only quote something meaningful the candidate actually said. "
            "- For weaknesses: Point out if they didn’t answer the question, gave off-topic or repetitive responses, or lacked structure. "
            "- If there were grammar or clarity issues that impacted professionalism or understanding, mention them directly. "
            
            "3. End with a single, punchy sentence of advice. Something like: 'Stay on topic and answer each question with purpose.' "
            
            "Scoring criteria: "
            "- 90–100: Strong, focused, well-articulated responses with clear examples and insights. "
            "- 70–89: Mostly good, but may lack detail or have minor clarity issues. "
            "- 50–69: Shows effort but lacks depth, structure, or clarity. May include vague answers or grammar issues. "
            "- 30–49: Weak communication, repeated off-topic answers, or poor structure. "
            "- 0–29: Failed to address the questions, gave irrelevant or incoherent answers."
        )
        evaluation_messages = [{"role": "system", "content": summary_system_prompt}] + history[1:]
        
        response = openai.chat.completions.create(model=AI_MODEL, messages=evaluation_messages, temperature=0.5)
        feedback_text = response.choices[0].message.content
    
    print(f"Generated Feedback: {feedback_text}")
    
    feedback_header = {"X-Feedback-Text": json.dumps({"text": feedback_text})}
    
    output_path_mp3 = os.path.join(TEMP_DIR, f"temp_audio_{time.time()}.mp3")
    generate_audio_via_cmd(feedback_text, output_path_mp3)
    
    return StreamingResponse(audio_streamer(output_path_mp3), media_type="audio/mpeg", headers=feedback_header)
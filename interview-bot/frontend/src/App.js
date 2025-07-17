import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const BACKEND_URL = 'http://localhost:8000';
const SILENT_AUDIO = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';

function App() {
  // This single state variable now controls the entire application flow.
  // 'welcome', 'starting', 'interview', 'recording', 'speaking', 'processing', 'summarizing', 'finished'
  const [appState, setAppState] = useState('welcome');
  
  const [messages, setMessages] = useState([]);
  const [finalFeedback, setFinalFeedback] = useState(null);

  const audioPlayerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const messagesEndRef = useRef(null);
  const [isAudioUnlocked, setIsAudioUnlocked] = useState(false);

  // This effect sets up the audio player and its 'ended' event listener
  useEffect(() => {
    if (!audioPlayerRef.current) {
      audioPlayerRef.current = new Audio();
    }
    const player = audioPlayerRef.current;
    
    const handleAudioEnd = () => {
      // --- This is the key state transition logic ---
      if (appState === 'summarizing') {
        // If the feedback audio just finished, we move to the 'finished' state.
        // The UI will now ONLY show the "Finish & Return" button.
        setAppState('finished');
      } else if (appState === 'speaking') {
        // Otherwise, it was a normal interview turn.
        setAppState('interview');
      }
    };

    player.addEventListener('ended', handleAudioEnd);
    return () => {
      player.removeEventListener('ended', handleAudioEnd);
    };
  }, [appState]); // The dependency on appState is crucial for this logic

  // Auto-scrolls the message container
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, finalFeedback]);

  const playAudio = async (audioBlob) => {
    try {
      const audioUrl = URL.createObjectURL(audioBlob);
      const player = audioPlayerRef.current;
      player.src = audioUrl;
      await player.play();
    } catch (error) {
      console.error("Audio playback failed:", error);
      // If playback fails, reset to a safe state
      if (appState === 'summarizing' || appState === 'speaking') {
        setAppState('finished');
      } else {
        setAppState('interview');
      }
    }
  };

  const startInterview = async () => {
    // This function now acts as the master "reset" and start function
    setMessages([]);
    setFinalFeedback(null);
    setAppState('starting');
    
    if (!isAudioUnlocked) {
      audioPlayerRef.current.src = SILENT_AUDIO;
      try { await audioPlayerRef.current.play(); } catch (e) { /* This is okay to fail silently */ }
      setIsAudioUnlocked(true);
      console.log("Audio context unlocked.");
    }
    
    try {
      const response = await axios.get(`${BACKEND_URL}/start_interview`, {
        responseType: 'blob',
      });
      setMessages([{ sender: 'bot', text: "Hello! Welcome to the mock interview session with the Malaysian Student Initiative. To begin, could you please tell me a little bit about yourself and what field of study you are planning to pursue?" }]);
      setAppState('speaking');
      playAudio(response.data);
    } catch (error) {
      console.error("Error starting interview:", error);
      setAppState('welcome');
      setMessages([{ sender: 'bot', text: 'Error connecting to the server. Please try again.' }]);
    }
  };

  const endInterview = async () => {
    if (appState === 'recording') {
        mediaRecorderRef.current.stop();
    }
    // Prevent this function from running if not in an active interview state
    if (appState !== 'interview' && appState !== 'speaking' && appState !== 'processing') return;
    
    const history = messages.map(msg => ({ role: msg.sender === 'user' ? 'user' : 'assistant', content: msg.text }));
    setAppState('summarizing');
    setMessages(prev => [...prev, { sender: 'bot', text: "Interview ended. Generating your final feedback..." }]);
    
    try {
      const response = await axios.post(`${BACKEND_URL}/end_interview_summary`, history, {
        headers: { 'Content-Type': 'application/json' },
        responseType: 'blob',
      });
      const feedbackHeader = response.headers['x-feedback-text'];
      if (feedbackHeader) {
          const feedbackData = JSON.parse(feedbackHeader);
          setFinalFeedback(feedbackData.text);
      }
      playAudio(response.data);
    } catch (error) {
      console.error("Error generating summary:", error);
      setFinalFeedback("An error occurred while generating your feedback.");
      setAppState('finished'); // Go to finished state even on error
    }
  };
  
  const sendAudioToServer = async (audioBlob) => {
    const history = messages.map(msg => ({ role: msg.sender === 'user' ? 'user' : 'assistant', content: msg.text }));
    const formData = new FormData();
    formData.append('audio', audioBlob, 'user_answer.webm');
    formData.append('history_json', JSON.stringify(history));
    setMessages(prev => [...prev, { sender: 'user', text: 'You spoke. (Processing...)' }]);
    setAppState('processing');
    try {
      const response = await axios.post(`${BACKEND_URL}/interview_turn`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      });
      const conversationData = JSON.parse(response.headers['x-conversation-data']);
      setMessages(conversationData.history.map(msg => ({ sender: msg.role === 'user' ? 'user' : 'bot', text: msg.content })));
      setAppState('speaking');
      playAudio(response.data);
    } catch (error) {
      console.error("Error during interview turn:", error);
      setAppState('interview');
    }
  };

  const startRecording = async () => { if (appState !== 'interview') return; try { const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: 'audio/webm' }); audioChunksRef.current = []; mediaRecorderRef.current.ondataavailable = (event) => { audioChunksRef.current.push(event.data); }; mediaRecorderRef.current.onstop = () => { const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' }); if (audioBlob.size > 1000) { sendAudioToServer(audioBlob); } else { setAppState('interview'); console.log("Empty recording detected."); } }; mediaRecorderRef.current.start(); setAppState('recording'); } catch (error) { console.error("Could not start recording:", error); } };
  const stopRecording = () => { if (mediaRecorderRef.current && appState === 'recording') { mediaRecorderRef.current.stop(); } };
  const handleRecordClick = () => { if (appState === 'recording') { stopRecording(); } else if (appState === 'interview') { startRecording(); } };
  const getButtonText = () => { if (appState === 'recording') return 'Stop Recording'; return 'Record Answer'; };
  const isDuringInterview = appState === 'interview' || appState === 'recording' || appState === 'speaking' || appState === 'processing';

  // --- RENDER LOGIC ---
  return (
    <div className="App">
      <audio ref={audioPlayerRef} style={{ display: 'none' }} />
      <header className="App-header">
        <h1>AI Interview Bot</h1>
        
        {appState === 'welcome' ? (
            <div className="welcome-box">
                <p>Welcome to the MSI Mock Scholarship Interview.</p>
                <p>Click the button below to start a new session. You will have 20 minutes to answer a series of questions designed to help you practice.</p>
                <p>Good luck!</p>
            </div>
        ) : (
          <div className="messages-container">
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.sender}`}>
                <p>{msg.text}</p>
              </div>
            ))}
            {finalFeedback && (
              <div className="message feedback">
                <h3>Final Feedback</h3>
                <p>{finalFeedback}</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
        
        <div className="controls">
          {appState === 'welcome' && <button onClick={startInterview} className="record-button">Start Interview</button>}
          
          {isDuringInterview && (
            <div className="button-group">
              <button onClick={handleRecordClick} disabled={appState !== 'interview' && appState !== 'recording'} className={appState === 'recording' ? 'recording' : 'record-button'}>
                {getButtonText()}
              </button>
              <button onClick={endInterview} className="end-button" disabled={appState !== 'interview' && appState !== 'recording'}>
                End Interview
              </button>
            </div>
          )}

          {appState === 'summarizing' && <p className="status-text">Generating & playing final feedback...</p>}

          {/* This is the final state, showing ONLY the reset button */}
          {appState === 'finished' && (
            <button onClick={() => setAppState('welcome')} className="record-button">
              Finish & Return to Main Menu
            </button>
          )}

          <p className="status-text">
            {appState === 'interview' && 'Ready for you to speak.'}
            {appState === 'processing' && 'Analyzing your response...'}
            {appState === 'speaking' && 'Listen to the interviewer.'}
            {appState === 'recording' && 'Recording... Click to stop.'}
            {appState === 'finished' && 'Interview complete. Click the button above to return.'}
            {appState === 'starting' && 'Connecting to the server...'}
          </p>
        </div>
      </header>
    </div>
  );
}

export default App;
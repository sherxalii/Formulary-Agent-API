import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FaMicrophone, FaPaperPlane, FaSpinner, FaStethoscope } from 'react-icons/fa';
import toast from 'react-hot-toast';
import './MediformAI.css';

// --- API call logic (with streaming, timeout, fallback, debug) ---
import {
  streamMediformAIResponse,
  fetchMediformDrugData
} from '../api/apiService';

function cleanResponse(text) {
  if (!text) return "";
  return text
    .replace(/[#*_`>]+/g, "") // Remove common markdown symbols
    .replace(/\n{3,}/g, "\n\n") // Limit max consecutive newlines
    .replace(/^\s+|\s+$/g, "") // Trim
    ;
}

async function fetchAIResponse(query, abortSignal, onStream, onError) {
  // Use Mediform AI streaming endpoint
  try {
    const payload = { query };
    const response = await streamMediformAIResponse(payload);
    if (!response.body) throw new Error('No response body');
    const reader = response.body.getReader();
    let result = '';
    let done = false;
    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      if (value) {
        const chunk = new TextDecoder().decode(value);
        result += chunk;
        onStream(result); // Update UI with accumulated result so far
      }
    }
    return result;
  } catch (err) {
    if (onError) onError(err);
    // Fallback: Try RxNorm/local DB for drug info if AI fails
    if (query && typeof query === 'string') {
      try {
        const drugRes = await fetchMediformDrugData(query);
        if (drugRes && drugRes.success) {
          let info = `**Drug:** ${drugRes.drugName || query}\n`;
          if (drugRes.rxNormId) info += `**RxNorm ID:** ${drugRes.rxNormId}\n`;
          if (drugRes.atcCode) info += `**ATC Code:** ${drugRes.atcCode}\n`;
          if (drugRes.indication) info += `**Indication:** ${drugRes.indication}\n`;
          if (drugRes.dosage) info += `**Dosage:** ${Array.isArray(drugRes.dosage) ? drugRes.dosage.join(', ') : drugRes.dosage}\n`;
          if (drugRes.sideEffects) info += `**Side Effects:** ${Array.isArray(drugRes.sideEffects) ? drugRes.sideEffects.join(', ') : drugRes.sideEffects}\n`;
          if (drugRes.contraindications) info += `**Contraindications:** ${Array.isArray(drugRes.contraindications) ? drugRes.contraindications.join(', ') : drugRes.contraindications}\n`;
          if (drugRes.interactions) info += `**Interactions:** ${Array.isArray(drugRes.interactions) ? drugRes.interactions.join(', ') : drugRes.interactions}\n`;
          if (drugRes.manufacturer) info += `**Manufacturer:** ${drugRes.manufacturer}\n`;
          onStream(info);
          return info;
        }
      } catch (fallbackErr) {
        if (onError) onError(fallbackErr);
      }
    }
    throw err;
  }
}

// --- Main Mediform AI Chatbot Modal ---
const MediformAI = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { id: 1, type: 'bot', content: 'Hello! I\'m Mediform AI. Ask me about any drug, coverage, or clinical question.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [streamed, setStreamed] = useState('');
  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);
  const cache = useRef({});
  // Debounce input
  useEffect(() => { if (open) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, streamed, open]);

  // --- External Trigger logic ---
  useEffect(() => {
    const handleOpenModal = () => setOpen(true);
    window.addEventListener('openAIAssistant', handleOpenModal);
    return () => window.removeEventListener('openAIAssistant', handleOpenModal);
  }, []);

  // --- Voice input logic ---
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-US';
      recognitionRef.current.onstart = () => setListening(true);
      recognitionRef.current.onend = () => setListening(false);
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInput(transcript);
        setTimeout(() => handleSend(transcript), 300);
      };
      recognitionRef.current.onerror = (event) => toast.error('Speech error: ' + event.error);
    }
  }, []);
  const startListening = () => {
    if (!recognitionRef.current) return toast.error('Speech not supported');
    recognitionRef.current.start();
  };

  // --- Send message logic ---
  const handleSend = async (override) => {
    const query = (override || input).trim();
    if (!query) return;
    if (loading) return;
    setInput('');
    setLoading(true);
    setStreamed('');
    setMessages((prev) => [...prev, { id: Date.now(), type: 'user', content: query }]);
    // Cache check
    if (cache.current[query]) {
      setMessages((prev) => [...prev, { id: Date.now() + 1, type: 'bot', content: cache.current[query] }]);
      setLoading(false);
      return;
    }
    // API call
    try {
      const full = await fetchAIResponse(query, null, (chunk) => {
        setStreamed(chunk); // Update streaming display in real-time
      }, (err) => {
        console.debug('AI error:', err);
      });
      cache.current[query] = full;
      setMessages((prev) => [...prev, { id: Date.now() + 2, type: 'bot', content: full }]);
    } catch (err) {
      setMessages((prev) => [...prev, { id: Date.now() + 3, type: 'bot', content: 'AI service temporarily unavailable. Showing basic drug info.' }]);
      // TODO: Fallback to RxNorm/local DB here
      console.error('AI error:', err);
    } finally {
      setLoading(false);
      setStreamed('');
    }
  };

  // --- UI ---
  return (
    <>
      {/* Floating Button */}
      <AnimatePresence>
        {!open && (
          <motion.button
            className="mediformai-fab"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            style={{
              position: 'fixed',
              bottom: 24,
              right: 24,
              zIndex: 10000,
              background: 'linear-gradient(135deg, #4f46e5 60%, #06b6d4 100%)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
              border: 'none',
              borderRadius: 999,
              width: 64,
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onClick={() => setOpen(true)}
            title="Open Mediform AI Assistant"
          >
            <FaStethoscope size={32} color="#fff" />
          </motion.button>
        )}
      </AnimatePresence>
      {/* Modal */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="mediformai-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0,0,0,0.18)',
              zIndex: 10001,
            }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              className="mediformai-modal"
              initial={{ scale: 0.95, opacity: 0, y: 40 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 40 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              style={{
                position: 'absolute',
                bottom: 24,
                right: 24,
                width: 380,
                height: 500,
                background: 'rgba(255,255,255,0.7)',
                backdropFilter: 'blur(24px)',
                borderRadius: 24,
                boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div style={{
                padding: '18px 24px 12px',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'transparent'
              }}>
                <span style={{
                  fontWeight: 700,
                  fontSize: 18,
                  color: '#4f46e5'
                }}>Mediform AI</span>
                <button onClick={() => setOpen(false)} style={{
                  background: 'none',
                  border: 'none',
                  fontSize: 22,
                  color: '#6b7280',
                  cursor: 'pointer'
                }}>&times;</button>
              </div>
              {/* Messages */}
              <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '16px 18px 0',
                background: 'transparent'
              }}>
                {messages.map((msg, idx) => (
                  <div key={msg.id} style={{
                    marginBottom: 12,
                    display: 'flex',
                    flexDirection: msg.type === 'user' ? 'row-reverse' : 'row',
                    alignItems: 'flex-end'
                  }}>
                    <div style={{
                      background: msg.type === 'user' ? 'rgba(79,70,229,0.12)' : 'rgba(255,255,255,0.85)',
                      color: msg.type === 'user' ? '#4f46e5' : '#22223b',
                      borderRadius: 18,
                      padding: '10px 16px',
                      maxWidth: 260,
                      fontSize: 15,
                      boxShadow: msg.type === 'user' ? '0 2px 8px rgba(79,70,229,0.08)' : '0 2px 8px rgba(0,0,0,0.04)',
                      border: msg.type === 'user' ? '1px solid #e0e7ff' : '1px solid #e5e7eb',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {msg.type === 'bot' ? cleanResponse(msg.content) : msg.content}
                      {idx === messages.length - 1 && loading && streamed && (
                        <span className="typing-indicator" style={{
                          marginLeft: 4,
                          color: '#a5b4fc'
                        }}>...</span>
                      )}
                    </div>
                  </div>
                ))}
                {/* Streaming message - show as the latest bot message during streaming */}
                {loading && streamed && (
                  <div style={{
                    marginBottom: 12,
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'flex-end'
                  }}>
                    <div style={{
                      background: 'rgba(255,255,255,0.85)',
                      color: '#22223b',
                      borderRadius: 18,
                      padding: '10px 16px',
                      maxWidth: 260,
                      fontSize: 15,
                      border: '1px solid #e5e7eb',
                      whiteSpace: 'pre-wrap', 
                    }}>
                      {cleanResponse(streamed)}
                      <span className="typing-indicator" style={{
                        marginLeft: 4,
                        color: '#a5b4fc'
                      }}>...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
              {/* Input */}
              <form
                onSubmit={e => { e.preventDefault(); handleSend(); }}
                style={{
                  padding: '12px 18px',
                  borderTop: '1px solid #e5e7eb',
                  background: 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  position: 'sticky',
                  bottom: 0,
                }}
              >
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Type your question..."
                  style={{
                    flex: 1,
                    borderRadius: 999,
                    border: '1px solid #e5e7eb',
                    padding: '10px 18px',
                    fontSize: 15,
                    outline: 'none',
                    background: 'rgba(255,255,255,0.9)',
                  }}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={startListening}
                  style={{
                    background: listening ? '#4f46e5' : '#fff',
                    color: listening ? '#fff' : '#4f46e5',
                    border: '1px solid #e5e7eb',
                    borderRadius: 999,
                    width: 40,
                    height: 40,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    marginRight: 2,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  disabled={loading}
                  title="Voice input"
                >
                  <FaMicrophone />
                </button>
                <button
                  type="submit"
                  style={{
                    background: '#4f46e5',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '50%',
                    width: 42,
                    height: 42,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    padding: 0,
                    boxShadow: '0 4px 12px rgba(79,70,229,0.25)',
                  }}
                  disabled={loading || !input.trim()}
                  title="Send"
                >
                  {loading ? (
                    <FaSpinner className="spinner" style={{ fontSize: 20 }} />
                  ) : (
                    <FaPaperPlane style={{ marginLeft: 2 }} />
                  )}
                </button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default MediformAI;

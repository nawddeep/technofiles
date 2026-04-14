import React, { useState, useRef, useEffect, useCallback } from 'react';
import LearningPathUI from './LearningPathUI';
import ChecklistUI from './ChecklistUI';
import { chatAPI, clearTokens } from '../services/api';

// ── JSON parser for AI UI responses ──────────────
const parseLearningPathJSON = (text) => {
    if (typeof text !== 'string') return { json: null, text };
    try {
        const jsonMatch = text.trim().match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
        if (jsonMatch && jsonMatch[1]) {
            const cleanJson = jsonMatch[1].trim();
            if ((cleanJson.startsWith('{') && cleanJson.endsWith('}')) ||
                (cleanJson.startsWith('[') && cleanJson.endsWith(']'))) {
                return {
                    json: JSON.parse(cleanJson),
                    text: text.replace(jsonMatch[0], '').trim()
                };
            }
        }
    } catch {
        // Malformed JSON — fall through to plain text
    }
    return { json: null, text };
};

// ── Inline confirm dialog (replaces window.confirm) ──────
function ConfirmDialog({ message, onConfirm, onCancel }) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="glass-panel rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
                <p className="text-on-surface font-body text-sm mb-6 text-center">{message}</p>
                <div className="flex gap-3">
                    <button
                        onClick={onCancel}
                        className="flex-1 py-2.5 rounded-full border border-black/10 text-on-surface-variant font-headline text-sm font-bold hover:bg-black/5 transition-all"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex-1 py-2.5 rounded-full bg-gradient-to-r from-primary to-secondary text-white font-headline text-sm font-bold hover:shadow-lg hover:shadow-primary/30 transition-all active:scale-[0.98]"
                    >
                        Clear Chat
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Main ChatArea component ───────────────────────────────
const ChatArea = () => {
    const [inputValue, setInputValue] = useState('');
    const [attachedFiles, setAttachedFiles] = useState([]);
    const [isListening, setIsListening] = useState(false);
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [speakingIdx, setSpeakingIdx] = useState(null);
    const [showConfirm, setShowConfirm] = useState(false);

    const fileInputRef = useRef(null);
    const recognitionRef = useRef(null);
    const messagesEndRef = useRef(null);
    
    // Get or create session ID
    const sessionId = useRef(localStorage.getItem('session_id') || 'chat-session').current;

    // Handle auth logout event
    useEffect(() => {
        const handleAuthLogout = () => {
            setMessages([]);
            setInputValue('');
            setAttachedFiles([]);
        };
        window.addEventListener('auth:logout', handleAuthLogout);
        return () => window.removeEventListener('auth:logout', handleAuthLogout);
    }, []);

    // ── Auto-scroll to bottom ──
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // ── Voice recognition setup ──
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return;

        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            setInputValue(transcript);
        };
        recognition.onerror = () => setIsListening(false);
        recognition.onend = () => setIsListening(false);

        recognitionRef.current = recognition;
    }, []);

    // ── Text-to-speech toggle ──
    const toggleSpeech = useCallback((text, idx) => {
        if (speakingIdx === idx) {
            window.speechSynthesis.cancel();
            setSpeakingIdx(null);
        } else {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.onend = () => setSpeakingIdx(null);
            utterance.onerror = () => setSpeakingIdx(null);
            window.speechSynthesis.speak(utterance);
            setSpeakingIdx(idx);
        }
    }, [speakingIdx]);

    // ── Send message ──
    const handleSend = async () => {
        if (!inputValue.trim() && attachedFiles.length === 0) return;

        const currentMessage = inputValue.trim();
        const currentFiles = [...attachedFiles];

        let displayText = currentMessage;
        if (currentFiles.length > 0) displayText += `\n[${currentFiles.length} image(s) attached]`;

        setMessages(prev => [...prev, { sender: 'user', text: displayText }]);
        setInputValue('');
        setAttachedFiles([]);
        setIsLoading(true);

        try {
            console.log('[ChatArea] Sending message:', { prompt: currentMessage, imageCount: currentFiles.length });
            
            // Convert files to base64
            const imagesBase64 = await Promise.all(currentFiles.map(file =>
                new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve({
                        mime_type: file.type || "image/jpeg",
                        data: reader.result.split(',')[1]
                    });
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                })
            ));

            const res = await chatAPI.sendMessage({ prompt: currentMessage, images: imagesBase64 }, sessionId);
            console.log('[ChatArea] Response status:', res.status);
            
            if (!res.ok) {
                const errorData = await res.json();
                console.error('[ChatArea] Error response:', errorData);
                setMessages(prev => [...prev, {
                    sender: 'ai',
                    text: `⚠️ ${errorData.error || 'Request failed'}`
                }]);
                return;
            }
            
            const data = await res.json();
            console.log('[ChatArea] AI response:', data);
            setMessages(prev => [...prev, { sender: 'ai', text: data.text }]);
        } catch (error) {
            console.error('[ChatArea] Exception:', error);
            setMessages(prev => [...prev, {
                sender: 'ai',
                text: `⚠️ ${error.message || 'Failed to get a response. Please try again.'}`
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    // ── New chat (with custom confirm dialog) ──
    const handleNewChat = () => setShowConfirm(true);

    const confirmNewChat = async () => {
        setShowConfirm(false);
        try {
            await chatAPI.clearChat(sessionId);
            setMessages([]);
        } catch {
            // Still clear UI even if server fails
            setMessages([]);
        }
    };

    // ── Voice input ──
    const handleVoiceClick = () => {
        if (!recognitionRef.current) {
            alert("Your browser doesn't support voice input.");
            return;
        }
        if (isListening) {
            recognitionRef.current.stop();
        } else {
            recognitionRef.current.start();
            setIsListening(true);
        }
    };

    return (
        <>
            {showConfirm && (
                <ConfirmDialog
                    message="Clear this chat? This will start a fresh conversation."
                    onConfirm={confirmNewChat}
                    onCancel={() => setShowConfirm(false)}
                />
            )}

            <div className={`flex flex-col items-center w-full h-full pb-6 px-4 ${messages.length === 0 ? 'justify-center' : 'justify-between'}`}>

                {/* Header / Messages */}
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center mb-6">
                        <h1 className="text-4xl md:text-5xl font-headline font-black text-on-surface tracking-tight text-center text-glow">
                            What's on the agenda today?
                        </h1>
                        <p className="text-on-surface-variant font-body text-sm mt-3 text-center opacity-70">
                            Ask SAAITA anything about academics, finance, or career.
                        </p>
                    </div>
                ) : (
                    <div className="w-full max-w-4xl flex flex-col flex-1 min-h-0 pt-4">
                        {/* New Chat Button */}
                        <div className="flex justify-end mb-3">
                            <button
                                onClick={handleNewChat}
                                className="bg-white/40 hover:bg-white/60 backdrop-blur-md border border-white/30 rounded-full px-4 py-1.5 text-sm font-medium text-on-surface-variant flex items-center gap-2 transition active:scale-95 shadow-sm"
                            >
                                <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current">
                                    <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
                                </svg>
                                New Chat
                            </button>
                        </div>

                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto flex flex-col gap-6 pb-6 pr-2 custom-scrollbar">
                            {messages.map((msg, idx) => (
                                <div key={idx} className={`max-w-[90%] rounded-2xl ${msg.sender === 'user'
                                    ? 'self-end bg-primary/10 border border-primary/20 p-4 shadow-sm'
                                    : 'self-start w-full'
                                    }`}>
                                    {msg.sender === 'ai' && (
                                        <div className="flex justify-between items-center mb-2">
                                            <strong className="text-primary font-headline text-lg tracking-wide">SAAITA</strong>
                                            <button
                                                onClick={() => toggleSpeech(msg.text, idx)}
                                                className={`p-1.5 rounded-full hover:bg-black/5 transition-colors ${speakingIdx === idx ? 'text-primary' : 'text-on-surface-variant'}`}
                                                title={speakingIdx === idx ? "Stop speaking" : "Read aloud"}
                                            >
                                                <svg viewBox="0 0 24 24" className="w-5 h-5 fill-current">
                                                    {speakingIdx === idx ? (
                                                        <path d="M6 6h12v12H6z" />
                                                    ) : (
                                                        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                                                    )}
                                                </svg>
                                            </button>
                                        </div>
                                    )}

                                    {(() => {
                                        if (msg.sender === 'ai') {
                                            const parsed = parseLearningPathJSON(msg.text);
                                            if (parsed.json) {
                                                return (
                                                    <div className="flex flex-col gap-4 w-full">
                                                        {parsed.text && (
                                                            <span className="whitespace-pre-wrap leading-relaxed text-on-surface text-[15px] font-body">
                                                                {parsed.text}
                                                            </span>
                                                        )}
                                                        {parsed.json.type === 'checklist' 
                                                            ? <ChecklistUI data={parsed.json} />
                                                            : <LearningPathUI data={parsed.json} />}
                                                    </div>
                                                );
                                            }
                                        }
                                        return (
                                            <span className="whitespace-pre-wrap leading-relaxed text-on-surface text-[15px] font-body">
                                                {msg.text}
                                            </span>
                                        );
                                    })()}
                                </div>
                            ))}

                            {isLoading && (
                                <div className="self-start flex items-center gap-2 ml-1">
                                    <div className="flex gap-1">
                                        {[0, 1, 2].map(i => (
                                            <span
                                                key={i}
                                                className="w-2 h-2 rounded-full bg-primary/60 animate-bounce"
                                                style={{ animationDelay: `${i * 0.15}s` }}
                                            />
                                        ))}
                                    </div>
                                    <span className="text-on-surface-variant text-sm font-medium">SAAITA is thinking...</span>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    </div>
                )}

                {/* Input Area */}
                <div className={`w-full max-w-4xl flex flex-col gap-3 mt-4 ${messages.length === 0 ? 'mb-10' : ''}`}>

                    {/* File Attachment Chips */}
                    {attachedFiles.length > 0 && (
                        <div className="flex gap-2 flex-wrap px-4">
                            {attachedFiles.map((file, idx) => (
                                <div key={idx} className="flex items-center gap-2 bg-white/60 backdrop-blur border border-white rounded-full px-3 py-1.5 text-xs text-on-surface-variant shadow-sm">
                                    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current">
                                        <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
                                    </svg>
                                    <span className="max-w-[150px] truncate">{file.name}</span>
                                    <button onClick={() => setAttachedFiles(prev => prev.filter((_, i) => i !== idx))} className="hover:text-primary transition-colors">
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Input Bar */}
                    <div className="glass-panel w-full flex items-center p-2 rounded-full shadow-lg">
                        <input
                            type="file"
                            multiple
                            ref={fileInputRef}
                            onChange={e => {
                                if (e.target.files) setAttachedFiles(prev => [...prev, ...Array.from(e.target.files)]);
                                e.target.value = '';
                            }}
                            className="hidden"
                        />

                        <button
                            className="p-3 text-on-surface-variant hover:text-primary transition-colors rounded-full hover:bg-black/5 mx-1"
                            title="Add attachment"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <svg viewBox="0 0 24 24" className="w-6 h-6 fill-current">
                                <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" />
                            </svg>
                        </button>

                        <input
                            type="text"
                            className="flex-1 bg-transparent border-none outline-none text-[15px] font-body text-on-surface px-2 placeholder:text-on-surface-variant/70"
                            placeholder={isListening ? "Listening... speak now" : "Ask SAAITA anything..."}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                        />

                        <button
                            className={`p-3 rounded-full transition-all mx-1 ${isListening ? 'text-primary bg-primary/10 animate-pulse' : 'text-on-surface-variant hover:text-primary hover:bg-black/5'}`}
                            title="Voice input"
                            onClick={handleVoiceClick}
                        >
                            <svg viewBox="0 0 24 24" className="w-6 h-6 fill-current">
                                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                            </svg>
                        </button>

                        <button
                            className={`p-3 rounded-full transition-all mx-1 flex items-center justify-center ${(inputValue.trim() || attachedFiles.length > 0)
                                ? 'bg-primary text-white shadow-md hover:scale-105 active:scale-95'
                                : 'bg-black/5 text-on-surface-variant/50 cursor-not-allowed'
                                }`}
                            onClick={handleSend}
                            disabled={!inputValue.trim() && attachedFiles.length === 0}
                            title="Send message"
                        >
                            <svg viewBox="0 0 24 24" className="w-[18px] h-[18px] fill-current -mr-0.5 mt-0.5">
                                <path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z" />
                            </svg>
                        </button>
                    </div>
                    <p className="text-center text-[11px] text-on-surface-variant/50 font-body">
                        SAAITA can make mistakes. Verify important information.
                    </p>
                </div>
            </div>
        </>
    );
};

export default ChatArea;

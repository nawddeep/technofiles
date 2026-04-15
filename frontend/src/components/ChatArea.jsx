import React, { useState, useRef, useEffect, useCallback } from 'react';
import { chatAPI } from '../services/api';
import { useVoiceRecognition } from '../hooks/useVoiceRecognition';
import MessageList from './MessageList';
import ChatInput from './ChatInput';

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
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [speakingIdx, setSpeakingIdx] = useState(null);
    const [showConfirm, setShowConfirm] = useState(false);

    const messagesEndRef = useRef(null);
    
    // Get or create session ID
    const sessionId = useRef(localStorage.getItem('session_id') || 'chat-session').current;

    // Use Custom Hook for Voice Recognition
    const { isListening, toggleListening } = useVoiceRecognition((transcript) => {
        setInputValue(prev => prev + ' ' + transcript);
    });

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

    // ── New chat ──
    const handleNewChat = () => setShowConfirm(true);

    const confirmNewChat = async () => {
        setShowConfirm(false);
        try {
            await chatAPI.clearChat(sessionId);
            setMessages([]);
        } catch {
            setMessages([]);
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

                        {/* Messages Component */}
                        <MessageList 
                            messages={messages}
                            isLoading={isLoading}
                            speakingIdx={speakingIdx}
                            toggleSpeech={toggleSpeech}
                            messagesEndRef={messagesEndRef}
                        />
                    </div>
                )}

                {/* Input Area Component */}
                <ChatInput 
                    inputValue={inputValue}
                    setInputValue={setInputValue}
                    attachedFiles={attachedFiles}
                    setAttachedFiles={setAttachedFiles}
                    handleSend={handleSend}
                    isListening={isListening}
                    handleVoiceClick={toggleListening}
                    messagesLength={messages.length}
                />
            </div>
        </>
    );
};

export default ChatArea;

import React, { useRef } from 'react';

const ChatInput = ({
    inputValue,
    setInputValue,
    attachedFiles,
    setAttachedFiles,
    handleSend,
    isListening,
    handleVoiceClick,
    messagesLength
}) => {
    const fileInputRef = useRef(null);

    return (
        <div className={`w-full max-w-4xl flex flex-col gap-3 mt-4 ${messagesLength === 0 ? 'mb-10' : ''}`}>
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
                                <svg className="w-4 h-4" file="none" stroke="currentColor" viewBox="0 0 24 24">
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
    );
};

export default ChatInput;

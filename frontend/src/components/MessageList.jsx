import React from 'react';
import LearningPathUI from './LearningPathUI';
import ChecklistUI from './ChecklistUI';
import { parseLearningPathJSON } from '../utils/chatUtils';

const MessageList = ({
    messages,
    isLoading,
    speakingIdx,
    toggleSpeech,
    messagesEndRef
}) => {
    return (
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
    );
};

export default MessageList;

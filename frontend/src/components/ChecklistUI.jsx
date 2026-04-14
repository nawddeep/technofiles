import React, { useState } from 'react';

const ChecklistUI = ({ data }) => {
    const [checkedItems, setCheckedItems] = useState({});

    const toggleCheck = (index) => {
        setCheckedItems(prev => ({
            ...prev,
            [index]: !prev[index]
        }));
    };

    if (!data || !data.title || !data.checkpoints) return null;

    return (
        <div className="bg-white/80 backdrop-blur-md border border-primary/20 rounded-2xl p-6 shadow-sm mt-2 mb-4 w-full">
            <h3 className="text-xl font-headline font-bold text-on-surface mb-6 border-b border-black/5 pb-3">
                {data.title}
            </h3>
            
            <div className="flex flex-col gap-4 relative">
                {/* Connecting line */}
                <div className="absolute left-[15px] top-4 bottom-4 w-0.5 bg-primary/20 z-0"></div>

                {data.checkpoints.map((cp, idx) => {
                    const isChecked = checkedItems[idx];
                    return (
                        <div 
                            key={idx} 
                            className={`flex gap-4 p-3 rounded-xl transition-all cursor-pointer relative z-10 hover:bg-black/5 ${isChecked ? 'opacity-60' : 'opacity-100'}`}
                            onClick={() => toggleCheck(idx)}
                        >
                            {/* Circle/Checkbox */}
                            <div className={`mt-1 flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors ${isChecked ? 'bg-primary border-primary' : 'bg-white border-primary/50'}`}>
                                {isChecked && (
                                    <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white">
                                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
                                    </svg>
                                )}
                            </div>

                            <div className="flex flex-col flex-1">
                                <h4 className={`text-[16px] font-bold font-headline transition-colors ${isChecked ? 'text-on-surface line-through decoration-2' : 'text-primary'}`}>
                                    {cp.task}
                                </h4>
                                {cp.description && (
                                    <p className="text-sm font-body text-on-surface-variant mt-1 leading-relaxed">
                                        {cp.description}
                                    </p>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default ChecklistUI;

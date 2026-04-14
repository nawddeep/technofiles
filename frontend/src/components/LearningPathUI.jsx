import React from 'react';

const RoadmapBlock = ({ difficulty, steps }) => {
    return (
        <div className="mb-8">
            {difficulty && (
                <h2 className="text-[20px] text-on-surface font-headline font-bold mb-4 pl-2 border-l-4 border-primary">
                    {difficulty} Path
                </h2>
            )}
            <div className="relative pl-[20px] border-l border-outline-variant/30 space-y-8">
                {steps.map((step, index) => {
                    const title = step.title || step.name || step.milestone || step.step || `Milestone ${index + 1}`;
                    const description = step.description || step.details || step.content || step.summary || '';
                    const formatDuration = step.duration || step.time || step.estimated_time || '';

                    return (
                        <div key={index} className="relative">
                            
                            {/* Milestone Marker */}
                            <div className="absolute -left-[40px] top-0 w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center font-bold z-10 shadow-[0_4px_10px_rgba(159,64,66,0.4)]">
                                <svg viewBox="0 0 24 24" className="w-5 h-5 fill-current">
                                    <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z"/>
                                </svg>
                            </div>

                            {/* Content Card */}
                            <div className="ml-6 glass-panel p-5 rounded-2xl transition hover:-translate-y-1 hover:shadow-lg">
                                <div className="flex justify-between items-start mb-2 gap-3">
                                    <h3 className="m-0 text-lg font-headline font-semibold text-on-surface">{title}</h3>
                                    {formatDuration && (
                                        <span className="bg-primary/10 text-primary px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap">
                                            {formatDuration}
                                        </span>
                                    )}
                                </div>
                                
                                {description && (
                                    <p className="m-0 text-on-surface-variant text-sm leading-relaxed font-body">
                                        {typeof description === 'string' ? description : JSON.stringify(description)}
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

const LearningPathUI = ({ data }) => {
    // Handle null / empty data gracefully
    if (!data) {
        return (
            <div className="glass-panel rounded-2xl p-8 text-center">
                <div className="text-4xl mb-4">🗺️</div>
                <h3 className="font-headline font-bold text-on-surface text-lg mb-2">No learning path yet</h3>
                <p className="text-on-surface-variant text-sm font-body">
                    Go to Chat and ask SAAITA: <em>"Give me a learning roadmap for [topic]"</em> — it will appear here.
                </p>
            </div>
        );
    }

    let roadmaps = [];
    
    const isDifficultyFormat = Array.isArray(data) && data.length > 0 && data[0].difficulty && data[0].path;

    if (isDifficultyFormat) {
        roadmaps = data;
    } else {
        let steps = [];
        if (Array.isArray(data)) {
            steps = data;
        } else if (data && typeof data === 'object') {
            for (const key in data) {
                if (Array.isArray(data[key])) {
                    steps = data[key];
                    break;
                }
            }
            if (steps.length === 0) {
                 steps = Object.values(data).filter(v => typeof v === 'object' && v !== null);
            }
        }
        
        if (!steps || steps.length === 0) {
            return (
                <div className="p-4 bg-surface-variant/50 rounded-xl w-full">
                    <p className="text-on-surface text-sm">Learning path data structure is unrecognizable.</p>
                    <pre className="text-xs mt-2 whitespace-pre-wrap text-on-surface-variant">
                        {JSON.stringify(data, null, 2)}
                    </pre>
                </div>
            );
        }
        roadmaps = [{ difficulty: null, path: steps }];
    }

    return (
        <div className="w-full mt-4">
            {roadmaps.map((roadmap, idx) => (
                <RoadmapBlock key={idx} difficulty={roadmap.difficulty} steps={roadmap.path} />
            ))}
        </div>
    );
};

export default LearningPathUI;

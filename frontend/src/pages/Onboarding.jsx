import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiOnboarding } from '../services/api';

const STEPS = [
  {
    id: 'intro',
    type: 'message',
    text: "Let's personalize your journey"
  },
  {
    id: 'journey',
    type: 'question',
    question: "Where are you in your academic journey?",
    options: [
      { label: "🎓 Undergraduate (UG)", value: "ug" },
      { label: "🎓 Graduate (PG)", value: "pg" },
      { label: "💼 Working Professional", value: "pro" }
    ]
  },
  {
    id: 'sub_journey',
    type: 'question',
    dynamicQuestion: (answers) => {
      if (answers.journey === 'ug') return "What year are you in?";
      if (answers.journey === 'pg') return "What is your main focus?";
      return "What brings you here today?";
    },
    dynamicOptions: (answers) => {
      if (answers.journey === 'ug') return [
        { label: "11th / 12th Grade", value: "highschool" },
        { label: "1st Year", value: "1st" },
        { label: "2nd Year", value: "2nd" },
        { label: "3rd Year", value: "3rd" },
        { label: "4th Year", value: "4th" }
      ];
      if (answers.journey === 'pg') return [
        { label: "Research", value: "research" },
        { label: "Coursework", value: "coursework" },
        { label: "Placement", value: "placement" }
      ];
      return [
        { label: "Upskilling", value: "upskilling" },
        { label: "Career Switch", value: "career_switch" },
        { label: "Finance Management", value: "finance" }
      ];
    }
  },
  {
    id: 'goal',
    type: 'question',
    question: "What is your primary goal right now?",
    options: [
      { label: "Managing Education Finances", value: "finance" },
      { label: "Acing Academics", value: "academics" },
      { label: "Career Readiness", value: "career" },
      { label: "Finding Scholarships/Grants", value: "scholarships" }
    ]
  },
  {
    id: 'confidence',
    type: 'question',
    question: "How confident are you with your current financial planning?",
    options: [
      { label: "Need help starting", value: "beginner" },
      { label: "I have basics sorted", value: "intermediate" },
      { label: "I'm a pro", value: "expert" }
    ]
  },
  {
    id: 'outro',
    type: 'message',
    text: "Ready to explore the SAAITA ecosystem?"
  }
];

export default function Onboarding() {
  const navigate = useNavigate();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [animating, setAnimating] = useState(false);
  const [saving, setSaving] = useState(false);

  const step = STEPS[currentStepIndex];

  useEffect(() => {
    // Intro message auto-advance
    if (step.id === 'intro') {
      const timer = setTimeout(() => handleNext(), 3000);
      return () => clearTimeout(timer);
    }
  }, [currentStepIndex]);

  const handleNext = async (value = null) => {
    if (value !== null) {
      setAnswers(prev => ({ ...prev, [step.id]: value }));
    }

    setAnimating(true);
    setTimeout(async () => {
      if (currentStepIndex < STEPS.length - 1) {
        setCurrentStepIndex(prev => prev + 1);
        setAnimating(false);
      } else {
        await finishOnboarding(answers, value);
      }
    }, 400); // Wait for fade out
  };

  const finishOnboarding = async (currentAnswers, lastValue) => {
    setSaving(true);
    try {
      const finalAnswers = { ...currentAnswers, confidence: lastValue };
      await apiOnboarding({ answers: finalAnswers });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      alert("Failed to save preferences. Please try again.");
      setAnimating(false);
      setSaving(false);
    }
  };

  const currentOptions = step.dynamicOptions ? step.dynamicOptions(answers) : step.options;
  const currentQuestionText = step.dynamicQuestion ? step.dynamicQuestion(answers) : step.question;

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center font-body selection:bg-primary/30">
      {/* Background Video */}
      <div className="absolute inset-0 z-0">
        <video
          autoPlay
          loop
          muted
          playsInline
          className="w-full h-full object-cover scale-105"
          src="/daisy-flower.mp4"
        ></video>
        {/* Soft elegant overlay */}
        <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"></div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30"></div>
      </div>

      <div className={`relative z-10 w-full max-w-xl p-8 flex flex-col items-center justify-center min-h-[400px] transition-opacity duration-300 ease-in-out ${animating ? 'opacity-0' : 'opacity-100'}`}>
        
        {step.type === 'message' && (
          <div className="text-center space-y-6">
            <h1 className="text-3xl md:text-5xl font-headline font-black text-white tracking-tight leading-tight">
              {step.text}
            </h1>
            {step.id === 'outro' && (
              <button
                onClick={() => handleNext()}
                disabled={saving}
                className="mt-8 px-8 py-3.5 bg-white text-black font-headline font-black tracking-[0.2em] uppercase text-xs rounded-full hover:scale-105 active:scale-95 transition-transform"
              >
                {saving ? 'PREPARING...' : "LET'S GO"}
              </button>
            )}
          </div>
        )}

        {step.type === 'question' && (
          <div className="w-full">
            <h2 className="text-2xl md:text-4xl font-headline font-bold text-white text-center mb-10 tracking-tight !leading-tight">
              {currentQuestionText}
            </h2>
            
            <div className="flex flex-col gap-3 w-full max-w-md mx-auto">
              {currentOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleNext(opt.value)}
                  className="w-full p-4 flex items-center justify-between bg-black/40 backdrop-blur-md border border-white/10 rounded-2xl text-left text-white group hover:bg-white/10 hover:border-white/30 transition-all duration-300 active:scale-[0.98]"
                >
                  <span className="font-headline font-semibold text-[15px] tracking-wide">{opt.label}</span>
                  <div className="w-6 h-6 rounded-full border border-white/20 flex items-center justify-center group-hover:border-primary group-hover:bg-primary/20 transition-colors">
                    <svg className="w-3 h-3 text-transparent group-hover:text-primary transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>

            {/* Stepper Dots (only for questions) */}
            <div className="flex justify-center gap-2 mt-12">
              {STEPS.filter(s => s.type === 'question').map((s, idx) => {
                const questionIndex = STEPS.filter(s => s.type === 'question').findIndex(x => x.id === step.id);
                return (
                  <div 
                    key={idx} 
                    className={`h-1.5 rounded-full transition-all duration-500 ${idx === questionIndex ? 'w-8 bg-white' : idx < questionIndex ? 'w-2 bg-white/50' : 'w-2 bg-white/20'}`}
                  />
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
